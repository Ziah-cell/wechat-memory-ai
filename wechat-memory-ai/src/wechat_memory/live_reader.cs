// Independent read-only UI Automation provider. No input or send APIs.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Web.Script.Serialization;
using System.Windows.Automation;

public static class LiveReader {
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
            != Convert.ToString(value,System.Globalization.CultureInfo.InvariantCulture))) throw new InvalidOperationException();
    }
    public static object Snapshot(string client, Dictionary<string,object> expected) {
        string path = Path.GetFullPath(client);
        if (!File.Exists(path) || !String.Equals(Path.GetFileName(path),"Weixin.exe",StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException();
        var processes = new Dictionary<int,Process>();
        foreach (var process in Process.GetProcessesByName("Weixin")) {
            try {
                if (String.Equals(process.MainModule.FileName,path,StringComparison.OrdinalIgnoreCase))
                    processes.Add(process.Id,process);
            } catch { throw new InvalidOperationException(); }
        }
        var targets = new List<IntPtr>();
        Exception failure = null;
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
        if (failure != null || targets.Count != 1 || IsIconic(targets[0])) throw new InvalidOperationException();
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
        if (!input || messageList == null) throw new InvalidOperationException();
        string listToken = Token(messageList);
        CheckBinding(expected,"list_token",listToken);
        var rows = new List<object>();
        for (var child=walker.GetFirstChild(messageList); child!=null; child=walker.GetNextSibling(child)) {
            SameProcess(child,(int)owner);
            if (rows.Count >= 256) throw new InvalidOperationException();
            var type = (ControlType)child.GetCurrentPropertyValue(AutomationElement.ControlTypeProperty);
            if (type != ControlType.ListItem) throw new InvalidOperationException();
            string kind = Property(child,AutomationElement.ClassNameProperty)=="mmui::ChatTextItemView" ? "text" : "other";
            string text = Property(child,AutomationElement.NameProperty);
            if (text.Length>10000) throw new InvalidOperationException();
            rows.Add(new {token=Token(child),text=text,kind=kind});
        }
        selected.Refresh();
        uint after;
        GetWindowThreadProcessId(handle,out after);
        if (selected.HasExited || selected.StartTime.ToUniversalTime().Ticks!=started || after!=owner || !IsWindowVisible(handle)
            || IsIconic(handle) || Property(root,AutomationElement.AutomationIdProperty)!=rootId || Token(messageList)!=listToken)
            throw new InvalidOperationException();
        return new {status="snapshot",process=(int)owner,started=started.ToString(),window=handle.ToInt64(),
                    root=rootId,list_token=listToken,rows=rows};
    }

    [STAThread] public static int Main(string[] args) {
        Console.OutputEncoding = new UTF8Encoding(false);
        try {
            if (args.Length!=1) return 3;
            var serializer = new JavaScriptSerializer();
            serializer.MaxJsonLength=4000000;
            string input = Console.In.ReadToEnd();
            if (input.Length>4096) return 3;
            var expected=serializer.Deserialize<Dictionary<string,object>>(input);
            Console.WriteLine(serializer.Serialize(Snapshot(args[0],expected)));
            return 0;
        } catch { return 3; }
    }
}
