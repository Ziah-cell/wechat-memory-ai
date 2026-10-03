// Independent read-only UI Automation provider. No input or send APIs.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows;
using System.Windows.Automation;

// A value captured on each side of a visual read. Matching text as well as
// UI identity/geometry detects in-place content changes on recycled controls.
public sealed class VisualRow {
    public readonly string Token, Kind, Text;
    public readonly Rect Bounds;
    public VisualRow(string token, string kind, string text, Rect bounds) {
        Token=token; Kind=kind; Text=text; Bounds=bounds;
    }
    public bool Matches(VisualRow other) {
        return other!=null && Token==other.Token && Kind==other.Kind && Text==other.Text && Bounds==other.Bounds;
    }
}

public sealed class SelectionRow {
    public readonly string Token, Kind, Text;
    public readonly int ControlTypeId;
    public SelectionRow(string token, string kind, string text, int controlTypeId) {
        Token=token; Kind=kind; Text=text; ControlTypeId=controlTypeId;
    }
    public bool Matches(SelectionRow other) {
        return other!=null && Token==other.Token && Kind==other.Kind && Text==other.Text
            && ControlTypeId==other.ControlTypeId;
    }
}

public static class LiveReader {
    // Fixed stage names only. External exception messages never leave the child.
    static string failureReason = "native_reader_failed";
    static Exception Failure(string reason) {
        failureReason = reason;
        return new InvalidOperationException();
    }
    delegate bool EnumWindow(IntPtr window, IntPtr parameter);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindow callback, IntPtr parameter);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);

    static string Property(AutomationElement item, AutomationProperty property) {
        return item.GetCurrentPropertyValue(property) as string ?? "";
    }
    static void SameProcess(AutomationElement item, int process) {
        if ((int)item.GetCurrentPropertyValue(AutomationElement.ProcessIdProperty) != process)
            throw new InvalidOperationException();
    }
    static string Token(AutomationElement item) {
        int[] ids = item.GetRuntimeId();
        if (ids == null || ids.Length < 1 || ids.Length > 32) throw new InvalidOperationException();
        return String.Join(".",Array.ConvertAll(ids, value => value.ToString(System.Globalization.CultureInfo.InvariantCulture)));
    }

    static System.Drawing.Rectangle ImageRect(Rect rect, System.Drawing.Rectangle window) {
        if(rect.IsEmpty || Double.IsNaN(rect.X) || Double.IsNaN(rect.Y) || Double.IsNaN(rect.Width) || Double.IsNaN(rect.Height)
                || rect.Width<=0 || rect.Height<=0 || rect.Width>100000 || rect.Height>100000
                || Math.Abs(rect.X)>100000 || Math.Abs(rect.Y)>100000) throw Failure("visual_capture_unavailable");
        return new System.Drawing.Rectangle((int)Math.Round(rect.X-window.X),(int)Math.Round(rect.Y-window.Y),
                                             (int)Math.Round(rect.Width),(int)Math.Round(rect.Height));
    }

    static void CheckBinding(Dictionary<string,object> expected, string key, object value) {
        if (expected != null && (!expected.ContainsKey(key) || Convert.ToString(expected[key],System.Globalization.CultureInfo.InvariantCulture)
            != Convert.ToString(value,System.Globalization.CultureInfo.InvariantCulture))) throw Failure("window_or_list_changed");
    }
    static void RecheckBinding(Process selected, IntPtr handle, uint owner, long started,
            AutomationElement root, string rootId, AutomationElement messageList, string listToken, bool allowMinimized=false) {
        failureReason = "window_binding_unavailable";
        selected.Refresh();
        uint after;
        GetWindowThreadProcessId(handle,out after);
        if(!allowMinimized && IsIconic(handle)) throw Failure("window_minimized");
        if(selected.HasExited || selected.StartTime.ToUniversalTime().Ticks!=started || after!=owner || !IsWindowVisible(handle)
                || Property(root,AutomationElement.AutomationIdProperty)!=rootId || Token(messageList)!=listToken)
            throw Failure("window_or_list_changed");
    }
    static void RecheckVisualRows(AutomationElement messageList, Rect listBounds,
            List<VisualRow> visualRows, uint owner, bool visualText, TreeWalker walker) {
        failureReason = "visual_snapshot_changed";
        if((Rect)messageList.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty)!=listBounds)
            throw new InvalidOperationException();
        int indexAfter=0;
        for(var child=walker.GetFirstChild(messageList); child!=null; child=walker.GetNextSibling(child)) {
            if(indexAfter>=visualRows.Count) throw new InvalidOperationException();
            SameProcess(child,(int)owner);
            if((ControlType)child.GetCurrentPropertyValue(AutomationElement.ControlTypeProperty)!=ControlType.ListItem)
                throw new InvalidOperationException();
            string kind=Property(child,AutomationElement.ClassNameProperty)=="mmui::ChatTextItemView" ? "text" : "other";
            var afterRow=new VisualRow(Token(child),kind,
                visualText ? Property(child,AutomationElement.NameProperty) : null,
                (Rect)child.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty));
            if(!visualRows[indexAfter].Matches(afterRow)) throw new InvalidOperationException();
            indexAfter++;
        }
        if(indexAfter!=visualRows.Count) throw new InvalidOperationException();
    }
    static List<SelectionRow> SelectionRows(AutomationElement list, uint owner, TreeWalker walker) {
        var rows = new List<SelectionRow>();
        for(var child=walker.GetFirstChild(list); child!=null; child=walker.GetNextSibling(child)) {
            if(rows.Count>=256) throw Failure("message_rows_unavailable");
            SameProcess(child,(int)owner);
            var type=(ControlType)child.GetCurrentPropertyValue(AutomationElement.ControlTypeProperty);
            string kind=Property(child,AutomationElement.ClassNameProperty)=="mmui::ChatTextItemView" ? "text" : "other";
            if((kind=="text" && type!=ControlType.CheckBox)
                    || (type!=ControlType.CheckBox && type!=ControlType.ListItem))
                throw Failure("selection_mode_required");
            // No pixel capture, layout inference, input, or sender guessing.
            string label=Property(child,AutomationElement.NameProperty);
            if(label.Length>10000) throw Failure("message_rows_unavailable");
            rows.Add(new SelectionRow(Token(child),kind,label,type.Id));
        }
        return rows;
    }
    public static object Snapshot(string client, Dictionary<string,object> expected, string mode) {
        bool layout = mode == "--layout";
        bool capabilities = mode == "--capabilities";
        bool visualText = mode == "--visual-text";
        bool windowState = mode == "--window-state";
        bool selectionText = mode == "--selection-text";
        // This explicit, already-bound diagnostic reads neither Name nor pixels.
        // The separate multiselect path reads labels; capture paths still reject minimization.
        if(windowState && expected==null) throw Failure("window_binding_unavailable");
        bool visual = mode == "--visual" || visualText;
        if(visual) {
            failureReason = "visual_capture_unavailable";
            VisualCapture.UsePhysicalCoordinates();
        }
        failureReason = "client_unavailable";
        string path = Path.GetFullPath(client);
        if (!File.Exists(path) || !String.Equals(Path.GetFileName(path),"Weixin.exe",StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException();
        var processes = new Dictionary<int,Process>();
        failureReason = "process_inspection_failed";
        foreach (var process in Process.GetProcessesByName("Weixin")) {
            try {
                if (String.Equals(process.MainModule.FileName,path,StringComparison.OrdinalIgnoreCase))
                    processes.Add(process.Id,process);
            } catch { throw new InvalidOperationException(); }
        }
        var targets = new List<IntPtr>();
        Exception failure = null;
        failureReason = "window_discovery_failed";
        EnumWindows(delegate(IntPtr window, IntPtr unused) {
            uint pid;
            GetWindowThreadProcessId(window,out pid);
            if (!processes.ContainsKey((int)pid) || !IsWindowVisible(window)) return true;
            try {
                var element = AutomationElement.FromHandle(window);
                SameProcess(element,(int)pid);
                string id = Property(element,AutomationElement.AutomationIdProperty);
                if (id.StartsWith("ChatSingleWindowwxid_",StringComparison.Ordinal)) targets.Add(window);
            } catch (Exception ex) { failure = ex; return false; }
            return true;
        },IntPtr.Zero);
        if (failure != null) throw new InvalidOperationException();
        if (targets.Count != 1) throw Failure("private_window_not_unique");
        bool minimized = IsIconic(targets[0]);
        if (minimized && !windowState && !selectionText) throw Failure("window_minimized");
        failureReason = "window_binding_unavailable";
        IntPtr handle = targets[0];
        uint owner;
        GetWindowThreadProcessId(handle,out owner);
        Process selected = processes[(int)owner];
        long started = selected.StartTime.ToUniversalTime().Ticks;
        var root = AutomationElement.FromHandle(handle);
        string rootId = Property(root,AutomationElement.AutomationIdProperty);
        // Reject replacement windows before traversing or reading their messages.
        CheckBinding(expected,"process",(int)owner);
        CheckBinding(expected,"started",started.ToString());
        CheckBinding(expected,"window",handle.ToInt64());
        CheckBinding(expected,"root",rootId);
        var walker = TreeWalker.RawViewWalker;
        failureReason = "message_tree_unavailable";
        var pending = new Queue<KeyValuePair<AutomationElement,int>>();
        pending.Enqueue(new KeyValuePair<AutomationElement,int>(root,0));
        AutomationElement messageList = null;
        int count = 0;
        bool input = false;
        bool cancelSelection = false;
        while (pending.Count > 0) {
            var current = pending.Dequeue();
            if (++count > 1024 || current.Value > 48) throw new InvalidOperationException();
            var node = current.Key;
            SameProcess(node,(int)owner);
            string id = Property(node,AutomationElement.AutomationIdProperty);
            if (id == "chat_input_field") input = true;
            if(selectionText && (ControlType)node.GetCurrentPropertyValue(AutomationElement.ControlTypeProperty)==ControlType.Button
                    && Property(node,AutomationElement.NameProperty)=="取消多选") cancelSelection=true;
            if (id == "chat_message_list") {
                if (messageList != null) throw new InvalidOperationException();
                messageList = node;
                continue;
            }
            for (var child=walker.GetFirstChild(node); child!=null; child=walker.GetNextSibling(child)) {
                if (pending.Count + count >= 1024) throw new InvalidOperationException();
                pending.Enqueue(new KeyValuePair<AutomationElement,int>(child,current.Value+1));
            }
        }
        if ((!selectionText && !input) || messageList == null) throw Failure("message_list_unavailable");
        if(selectionText && (!cancelSelection || input)) throw Failure("selection_mode_required");
        failureReason = "message_list_unavailable";
        string listToken = Token(messageList);
        CheckBinding(expected,"list_token",listToken);
        if(selectionText) {
            failureReason="message_rows_unavailable";
            string peer=Property(root,AutomationElement.NameProperty);
            if(String.IsNullOrWhiteSpace(peer) || peer.Length>256 || peer.IndexOfAny(new char[]{'\r','\n','\t','\0'})>=0)
                throw Failure("selection_mode_required");
            var before=SelectionRows(messageList,owner,walker);
            RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken,true);
            var after=SelectionRows(messageList,owner,walker);
            if(before.Count!=after.Count) throw Failure("selection_snapshot_changed");
            var selectionRows=new List<object>();
            for(int i=0;i<before.Count;i++) {
                if(!before[i].Matches(after[i])) throw Failure("selection_snapshot_changed");
                selectionRows.Add(new {token=before[i].Token,kind=before[i].Kind,text=before[i].Text});
            }
            RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken,true);
            if(Property(root,AutomationElement.NameProperty)!=peer || IsIconic(handle)!=minimized)
                throw Failure("selection_snapshot_changed");
            return new {status="selection_text_snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                root=rootId,list_token=listToken,peer_name=peer,minimized=minimized,rows=selectionRows};
        }
        if(windowState) {
            failureReason = "capabilities_unavailable";
            int total=0, texts=0, offscreen=0, bounded=0, textPatterns=0, childTexts=0;
            Rect bounds=(Rect)messageList.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty);
            bool boundsUsable=!bounds.IsEmpty && bounds.Width>0 && bounds.Height>0
                && !Double.IsInfinity(bounds.Width) && !Double.IsInfinity(bounds.Height)
                && !Double.IsNaN(bounds.Width) && !Double.IsNaN(bounds.Height);
            object pattern;
            bool scroll=messageList.TryGetCurrentPattern(ScrollPattern.Pattern,out pattern);
            for(var child=walker.GetFirstChild(messageList); child!=null; child=walker.GetNextSibling(child)) {
                if(++total>256) throw new InvalidOperationException();
                SameProcess(child,(int)owner);
                if(Property(child,AutomationElement.ClassNameProperty)!="mmui::ChatTextItemView") continue;
                texts++;
                if((bool)child.GetCurrentPropertyValue(AutomationElement.IsOffscreenProperty)) offscreen++;
                Rect rowBounds=(Rect)child.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty);
                if(!rowBounds.IsEmpty && rowBounds.Width>0 && rowBounds.Height>0
                    && !Double.IsInfinity(rowBounds.Width) && !Double.IsInfinity(rowBounds.Height)
                    && !Double.IsNaN(rowBounds.Width) && !Double.IsNaN(rowBounds.Height)) bounded++;
                if(child.TryGetCurrentPattern(TextPattern.Pattern,out pattern)) textPatterns++;
                if(walker.GetFirstChild(child)!=null) childTexts++;
            }
            RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken,true);
            if(IsIconic(handle)!=minimized) throw Failure("window_or_list_changed");
            return new {status="window_state_snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                root=rootId,list_token=listToken,minimized=minimized,list_bounds_usable=boundsUsable,list_scroll_pattern=scroll,
                rows=total,text_rows=texts,offscreen_text_rows=offscreen,bounded_text_rows=bounded,
                text_pattern_rows=textPatterns,child_text_rows=childTexts};
        }
        var rows = new List<object>();
        var visualRows = new List<VisualRow>();
        var rowIds = new HashSet<string>(StringComparer.Ordinal);
        bool scrollAvailable = false;
        bool? verticalScrollable = null;
        double? verticalPercent = null;
        if (capabilities) {
            failureReason = "capabilities_unavailable";
            object pattern;
            scrollAvailable = messageList.TryGetCurrentPattern(ScrollPattern.Pattern,out pattern);
            if (scrollAvailable) {
                var info = ((ScrollPattern)pattern).Current;
                verticalScrollable = info.VerticallyScrollable;
                verticalPercent = info.VerticalScrollPercent;
            }
        }
        Rect listBounds = Rect.Empty;
        if (layout || visual) {
            failureReason = "layout_unavailable";
            listBounds = (Rect)messageList.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty);
            if (listBounds.IsEmpty || listBounds.Width <= 0) throw new InvalidOperationException();
        }
        failureReason = "message_rows_unavailable";
        for (var child=walker.GetFirstChild(messageList); child!=null; child=walker.GetNextSibling(child)) {
            SameProcess(child,(int)owner);
            if (rows.Count >= 256) throw new InvalidOperationException();
            var type = (ControlType)child.GetCurrentPropertyValue(AutomationElement.ControlTypeProperty);
            if (type != ControlType.ListItem) throw new InvalidOperationException();
            string kind = Property(child,AutomationElement.ClassNameProperty)=="mmui::ChatTextItemView" ? "text" : "other";
            if (visual) {
                failureReason = "visual_capture_unavailable";
                string body=visualText ? Property(child,AutomationElement.NameProperty) : null;
                if(body!=null && body.Length>10000) throw new InvalidOperationException();
                visualRows.Add(new VisualRow(Token(child),kind,body,
                    (Rect)child.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty)));
                // Count still bounds enumeration even before visual rows exist.
                rows.Add(null);
                failureReason = "message_rows_unavailable";
                continue;
            }
            if (capabilities) {
                failureReason = "capabilities_unavailable";
                string rowId = Property(child,AutomationElement.AutomationIdProperty);
                if (rowId.Length > 0) rowIds.Add(rowId);
                rows.Add(new {token=Token(child),kind=kind,
                    automation_id=rowId.Length>0,
                    help_text=Property(child,AutomationElement.HelpTextProperty).Length>0,
                    item_status=Property(child,AutomationElement.ItemStatusProperty).Length>0,
                    item_type=Property(child,AutomationElement.ItemTypeProperty).Length>0,
                    labeled_by=child.GetCurrentPropertyValue(AutomationElement.LabeledByProperty) is AutomationElement,
                    text_pattern=(bool)child.GetCurrentPropertyValue(AutomationElement.IsTextPatternAvailableProperty)});
                failureReason = "message_rows_unavailable";
                continue;
            }
            if (layout) {
                failureReason = "layout_unavailable";
                Rect bounds = (Rect)child.GetCurrentPropertyValue(AutomationElement.BoundingRectangleProperty);
                if (bounds.IsEmpty || bounds.Width <= 0) throw new InvalidOperationException();
                var firstChild = walker.GetFirstChild(child);
                if (firstChild != null) SameProcess(firstChild,(int)owner);
                rows.Add(new {token=Token(child),kind=kind,
                    left_gap=(bounds.Left-listBounds.Left)/listBounds.Width,
                    right_gap=(listBounds.Right-bounds.Right)/listBounds.Width,
                    width_ratio=bounds.Width/listBounds.Width,has_children=firstChild!=null});
                failureReason = "message_rows_unavailable";
                continue;
            }
            string text = Property(child,AutomationElement.NameProperty);
            if (text.Length>10000) throw new InvalidOperationException();
            rows.Add(new {token=Token(child),text=text,kind=kind});
        }
        int visualCaptureAttempts=0;
        if (visual) {
            for(int attempt=1; attempt<=3; attempt++) {
                visualCaptureAttempts=attempt;
                RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken);
                RecheckVisualRows(messageList,listBounds,visualRows,owner,visualText,walker);
                failureReason = "visual_capture_unavailable";
                var classifications=new List<VisualClassification>();
                using(var frame=VisualCapture.Take(handle)) {
                    // Each attempt wholly replaces the preceding frame's rows.
                    rows.Clear();
                    var listRect=ImageRect(listBounds,frame.Bounds);
                    foreach(var row in visualRows) {
                        var rowRect=ImageRect(row.Bounds,frame.Bounds);
                        var classification=row.Kind=="text" ? VisualDirection.Analyze(frame.Image,listRect,rowRect,frame.Scale)
                            : new VisualClassification("unknown","not_text");
                        classifications.Add(classification);
                        if(visualText) rows.Add(new {token=row.Token,kind=row.Kind,text=row.Text,direction=classification.Direction});
                        else rows.Add(new {token=row.Token,kind=row.Kind,direction=classification.Direction,reason=classification.Reason});
                    }
                }
                RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken);
                RecheckVisualRows(messageList,listBounds,visualRows,owner,visualText,walker);
                RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken);
                // Other unknowns and mixed evidence are never retried/promoted.
                if(!VisualRetry.ShouldRetry(classifications,attempt)) break;
                System.Threading.Thread.Sleep(50);
            }
        }
        RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken);
        if (capabilities)
            return new {status="capability_snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                root=rootId,list_token=listToken,rows=rows,scroll_pattern=scrollAvailable,
                vertical_scrollable=verticalScrollable,vertical_scroll_percent=verticalPercent,distinct_automation_ids=rowIds.Count};
        if (visual && !visualText)
            return new {status="visual_snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                root=rootId,list_token=listToken,rows=rows,capture_attempts=visualCaptureAttempts};
        return new {status=layout ? "layout_snapshot" : visualText ? "visual_text_snapshot" : visual ? "visual_snapshot" : "snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                    root=rootId,list_token=listToken,rows=rows};
    }

    [STAThread] public static int Main(string[] args) {
        Console.OutputEncoding = new UTF8Encoding(false);
        try {
            if (args.Length!=1 && (args.Length!=2 || (args[1]!="--layout" && args[1]!="--capabilities" && args[1]!="--visual" && args[1]!="--visual-text" && args[1]!="--window-state" && args[1]!="--selection-text"))) return 3;
            var serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength=4000000;
            string input = Console.In.ReadToEnd();
            if (input.Length>4096) return 3;
            var expected=serializer.Deserialize<Dictionary<string,object>>(input);
            Console.WriteLine(serializer.Serialize(Snapshot(args[0],expected,args.Length==2 ? args[1] : "")));
            return 0;
        } catch {
            var serializer = new JavaScriptSerializer();
            Console.WriteLine(serializer.Serialize(new {status="reader_error",reason=failureReason}));
            return 3;
        }
    }
}
