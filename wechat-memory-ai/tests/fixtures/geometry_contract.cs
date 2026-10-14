// Pure rectangle/scalar contracts. No bitmap, window, UIA or native API calls.
using System;
using System.Drawing;
using System.Reflection;

class GeometryContract {
    static MethodInfo gate = typeof(VisualDirection).GetMethod("GeometryFailure");
    static Rectangle list = new Rectangle(0, 0, 600, 300);
    static Rectangle row = new Rectangle(0, 0, 600, 72);
    static void Check(string name, bool image, int width, int height,
                      Rectangle area, Rectangle item, double scale) {
        string reason = gate == null ? "missing_geometry_diagnostic" :
            (string)gate.Invoke(null, new object[] {image, width, height, area, item, scale});
        Console.WriteLine(name + "=" + (reason ?? "valid"));
    }
    static void Main() {
        Check("normal", true, 600, 400, list, row, 1);
        Check("missing", false, 0, 0, Rectangle.Empty, Rectangle.Empty, Double.NaN);
        Check("nan", true, 600, 400, list, row, Double.NaN);
        Check("infinite", true, 600, 400, list, row, Double.PositiveInfinity);
        Check("small_scale", true, 600, 400, list, row, .74);
        Check("large_scale", true, 600, 400, list, row, 3.01);
        Check("empty_list", true, 600, 400, Rectangle.Empty, row, 1);
        Check("narrow", true, 600, 400, list, new Rectangle(0, 0, 299, 72), 1);
        Check("short", true, 600, 400, list, new Rectangle(0, 0, 600, 35), 1);
        Check("list_outside", true, 599, 400, list, row, 1);
        Check("row_above", true, 600, 400, list, new Rectangle(0, -1, 600, 72), 1);
        Check("row_below", true, 600, 400, list, new Rectangle(0, 229, 600, 72), 1);
        Check("left_gap", true, 600, 400, list, new Rectangle(3, 0, 597, 72), 1);
        Check("right_gap", true, 600, 400, list, new Rectangle(0, 0, 597, 72), 1);
        Check("aligned_boundary", true, 600, 400, list, new Rectangle(2, 0, 596, 36), 1);
        Check("scaled_minimum", true, 900, 600, new Rectangle(0, 0, 450, 300), new Rectangle(0, 246, 450, 54), 1.5);
        Check("scaled_short", true, 900, 600, new Rectangle(0, 0, 450, 300), new Rectangle(0, 0, 450, 53), 1.5);
        Check("scaled_narrow", true, 900, 600, new Rectangle(0, 0, 450, 300), new Rectangle(0, 0, 449, 54), 1.5);
        Check("min_scale", true, 600, 400, list, row, .75);
        Check("max_scale", true, 900, 600, new Rectangle(0, 0, 900, 600), new Rectangle(0, 0, 900, 108), 3);
        var classification = VisualDirection.Analyze(null, list, row, 1);
        var detail = typeof(VisualClassification).GetField("GeometryReason");
        Console.WriteLine("null_analysis=" + classification.Direction + "/" + classification.Reason + "/" +
            (detail == null ? "missing_geometry_diagnostic" : detail.GetValue(classification)));
    }
}
