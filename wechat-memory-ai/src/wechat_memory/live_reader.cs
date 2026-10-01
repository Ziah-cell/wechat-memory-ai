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

    static void CheckBinding(Dictionary<string,object> expected, string key, object value) {
        if (expected != null && (!expected.ContainsKey(key) || Convert.ToString(expected[key],System.Globalization.CultureInfo.InvariantCulture)
            != Convert.ToString(value,System.Globalization.CultureInfo.InvariantCulture))) throw Failure("window_or_list_changed");
    }
    public static object Snapshot(string client, Dictionary<string,object> expected, string mode) {
        bool layout = mode == "--layout";
        bool capabilities = mode == "--capabilities";
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
        if (IsIconic(targets[0])) throw Failure("window_minimized");
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
        failureReason = "message_list_unavailable";
        string listToken = Token(messageList);
        CheckBinding(expected,"list_token",listToken);
        var rows = new List<object>();
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
        if (layout) {
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
        failureReason = "window_binding_unavailable";
        selected.Refresh();
        uint after;
        GetWindowThreadProcessId(handle,out after);
        if (IsIconic(handle)) throw Failure("window_minimized");
        if (selected.HasExited || selected.StartTime.ToUniversalTime().Ticks!=started || after!=owner || !IsWindowVisible(handle)
            || Property(root,AutomationElement.AutomationIdProperty)!=rootId || Token(messageList)!=listToken)
            throw Failure("window_or_list_changed");
        if (capabilities)
            return new {status="capability_snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                root=rootId,list_token=listToken,rows=rows,scroll_pattern=scrollAvailable,
                vertical_scrollable=verticalScrollable,vertical_scroll_percent=verticalPercent,distinct_automation_ids=rowIds.Count};
        return new {status=layout ? "layout_snapshot" : "snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                    root=rootId,list_token=listToken,rows=rows};
    }

    [STAThread] public static int Main(string[] args) {
        Console.OutputEncoding = new UTF8Encoding(false);
        try {
            if (args.Length!=1 && (args.Length!=2 || (args[1]!="--layout" && args[1]!="--capabilities"))) return 3;
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
