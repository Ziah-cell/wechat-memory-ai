# Independent implementation using Windows UIA. No third-party automation code.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -ReferencedAssemblies UIAutomationClient,UIAutomationTypes -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Windows.Automation;

namespace WechatReadOnly {
    public sealed class Snapshot {
        public int Nodes;
        public int OnscreenNodes;
        public bool Limited;
        public bool ScopeChanged;
        public Dictionary<string, int> ControlTypes = new Dictionary<string, int>();
    }

    public static class TreeProbe {
        // No Name, AutomationId, Value, Text, RuntimeId, focus or action patterns.
        // Use individual properties: AutomationElement.Current includes names.
        public static Snapshot Read(IntPtr handle, int processId, int maxNodes, int maxDepth) {
            if (maxNodes < 1 || maxNodes > 256 || maxDepth < 0 || maxDepth > 16)
                throw new ArgumentOutOfRangeException();
            Snapshot result = new Snapshot();
            AutomationElement root = AutomationElement.FromHandle(handle);
            Walk(root, processId, 0, maxNodes, maxDepth, result);
            return result;
        }

        private static void Walk(AutomationElement node, int processId, int depth,
                                 int maxNodes, int maxDepth, Snapshot result) {
            if (node == null || result.ScopeChanged) return;
            if (result.Nodes >= maxNodes) { result.Limited = true; return; }
            int owner = (int)node.GetCurrentPropertyValue(AutomationElement.ProcessIdProperty);
            if (owner != processId) { result.ScopeChanged = true; return; }
            ControlType type = (ControlType)node.GetCurrentPropertyValue(AutomationElement.ControlTypeProperty);
            bool offscreen = (bool)node.GetCurrentPropertyValue(AutomationElement.IsOffscreenProperty);
            result.Nodes++;
            if (!offscreen) result.OnscreenNodes++;
            string key = type.Id.ToString(System.Globalization.CultureInfo.InvariantCulture);
            if (!result.ControlTypes.ContainsKey(key)) result.ControlTypes[key] = 0;
            result.ControlTypes[key]++;
            // Conservatively mark an incomplete traversal without probing beyond the bound.
            if (depth >= maxDepth || result.Nodes >= maxNodes) { result.Limited = true; return; }
            TreeWalker walker = TreeWalker.RawViewWalker;
            AutomationElement child = walker.GetFirstChild(node);
            while (child != null) {
                Walk(child, processId, depth + 1, maxNodes, maxDepth, result);
                if (result.ScopeChanged) return;
                if (result.Nodes >= maxNodes) { result.Limited = true; return; }
                child = walker.GetNextSibling(child);
            }
        }
    }
}
'@
