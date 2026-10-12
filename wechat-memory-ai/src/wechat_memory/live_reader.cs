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

public static class LiveReader {
    static bool timingEnabled;
    static readonly Stopwatch timingClock = Stopwatch.StartNew();
    // Only literals are passed here; no UI values, identity or exception text.
    // Flush each boundary so a killed child can still explain its last stage.
    static void Timing(string stage) {
        if(!timingEnabled) return;
        try {
            Console.Error.WriteLine("wmrd1:"+stage+":"+timingClock.ElapsedMilliseconds.ToString(System.Globalization.CultureInfo.InvariantCulture));
            Console.Error.Flush();
        } catch { /* Diagnostics cannot change snapshot acceptance. */ }
    }
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
            AutomationElement root, string rootId, AutomationElement messageList, string listToken) {
        failureReason = "window_binding_unavailable";
        selected.Refresh();
        uint after;
        GetWindowThreadProcessId(handle,out after);
        if(IsIconic(handle)) throw Failure("window_minimized");
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
    public static object Snapshot(string client, Dictionary<string,object> expected, string mode) {
        bool layout = mode == "--layout";
        bool capabilities = mode == "--capabilities";
        bool visualText = mode == "--visual-text";
        bool visual = mode == "--visual" || visualText;
        if(visual) {
            failureReason = "visual_capture_unavailable";
            VisualCapture.UsePhysicalCoordinates();
        }
        Timing("client_lookup");
        failureReason = "client_unavailable";
        string path = Path.GetFullPath(client);
        if (!File.Exists(path) || !String.Equals(Path.GetFileName(path),"Weixin.exe",StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException();
        Timing("process_lookup");
        var processes = new Dictionary<int,Process>();
        failureReason = "process_inspection_failed";
        foreach (var process in Process.GetProcessesByName("Weixin")) {
            try {
                if (String.Equals(process.MainModule.FileName,path,StringComparison.OrdinalIgnoreCase))
                    processes.Add(process.Id,process);
            } catch { throw new InvalidOperationException(); }
        }
        Timing("window_lookup");
        var targets = new List<IntPtr>();
        int visibleWindows = 0, identifiedWindows = 0;
        Exception failure = null;
        failureReason = "window_discovery_failed";
        EnumWindows(delegate(IntPtr window, IntPtr unused) {
            uint pid;
            GetWindowThreadProcessId(window,out pid);
            if (!processes.ContainsKey((int)pid) || !IsWindowVisible(window)) return true;
            visibleWindows++;
            try {
                var element = AutomationElement.FromHandle(window);
                SameProcess(element,(int)pid);
                string id = Property(element,AutomationElement.AutomationIdProperty);
                if (!String.IsNullOrEmpty(id)) identifiedWindows++;
                if (id.StartsWith("ChatSingleWindowwxid_",StringComparison.Ordinal)) targets.Add(window);
            } catch (Exception ex) { failure = ex; return false; }
            return true;
        },IntPtr.Zero);
        if (failure != null) throw new InvalidOperationException();
        // An inaccessible tree is not evidence that the user failed to open
        // the chat. Never fall back to a title, screen coordinates or another
        // window when UIA cannot identify any visible WeChat root.
        if (targets.Count == 0 && visibleWindows > 0 && identifiedWindows == 0)
            throw Failure("window_identity_unavailable");
        if (targets.Count != 1) throw Failure("private_window_not_unique");
        if (IsIconic(targets[0])) throw Failure("window_minimized");
        Timing("binding_check");
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
        Timing("tree_lookup");
        var walker = TreeWalker.RawViewWalker;
        failureReason = "message_tree_unavailable";
        var pending = new Queue<KeyValuePair<AutomationElement,int>>();
        pending.Enqueue(new KeyValuePair<AutomationElement,int>(root,0));
        AutomationElement messageList = null;
        int count = 0;
        bool input = false;
        while (pending.Count > 0) {
            var current = pending.Dequeue();
            if (++count > 1024 || current.Value > 48) throw new InvalidOperationException();
            var node = current.Key;
            SameProcess(node,(int)owner);
            string id = Property(node,AutomationElement.AutomationIdProperty);
            if (id == "chat_input_field") input = true;
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
        if (!input || messageList == null) throw Failure("message_list_unavailable");
        Timing("list_binding");
        failureReason = "message_list_unavailable";
        string listToken = Token(messageList);
        CheckBinding(expected,"list_token",listToken);
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
        Timing("rows_first");
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
        Timing("visual_capture");
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
        Timing("binding_final");
        RecheckBinding(selected,handle,owner,started,root,rootId,messageList,listToken);
        Timing("snapshot_ready");
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
        timingEnabled = true;
        Timing("started");
        try {
            if (args.Length!=1 && (args.Length!=2 || (args[1]!="--layout" && args[1]!="--capabilities" && args[1]!="--visual" && args[1]!="--visual-text"))) return 3;
            var serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength=4000000;
            Timing("request_read");
            string input = Console.In.ReadToEnd();
            if (input.Length>4096) return 3;
            var expected=serializer.Deserialize<Dictionary<string,object>>(input);
            object snapshot = Snapshot(args[0],expected,args.Length==2 ? args[1] : "");
            Timing("serializing");
            Console.WriteLine(serializer.Serialize(snapshot));
            Console.Out.Flush();
            Timing("completed");
            return 0;
        } catch {
            var serializer = new JavaScriptSerializer();
            Console.WriteLine(serializer.Serialize(new {status="reader_error",reason=failureReason}));
            return 3;
        }
    }
}
