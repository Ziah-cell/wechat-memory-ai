// Pure rectangle/scalar inputs. No bitmaps, UIA, windows or native API calls.
using System;
using System.Drawing;
using System.Reflection;

class VisibleRowContract {
    static MethodInfo analyze = typeof(VisualDirection).GetMethod("AnalysisGeometry");
    static Rectangle list = new Rectangle(10,20,600,300);
    static void Check(string name, Rectangle area, Rectangle row, double scale, bool image, int width, int height) {
        if(analyze==null) { Console.WriteLine(name+"=missing_visible_geometry"); return; }
        object[] args = {image,width,height,area,row,scale,Rectangle.Empty};
        string failure=(string)analyze.Invoke(null,args);
        Rectangle visible=(Rectangle)args[6];
        if(failure!=null) {
            Console.WriteLine(name+"="+failure+"/"+(visible.IsEmpty ? "empty" : "unsafe"));
        } else {
            Console.WriteLine(name+"=valid/"+visible.X+","+visible.Y+","+visible.Width+","+visible.Height);
            if(!area.Contains(visible) || !new Rectangle(0,0,width,height).Contains(visible))
                throw new Exception("analysis rectangle escaped allowed area");
        }
    }
    static void Main() {
        Check("contained",list,new Rectangle(10,248,600,72),1,true,800,600);
        Check("bottom_one",list,new Rectangle(10,249,600,72),1,true,800,600);
        Check("observed_scaled",list,new Rectangle(10,237,600,84),1.5,true,800,600);
        Check("bottom_two",list,new Rectangle(10,250,600,72),1,true,800,600);
        Check("top_one",list,new Rectangle(10,19,600,72),1,true,800,600);
        Check("left_one",list,new Rectangle(9,249,601,72),1,true,800,600);
        Check("right_one",list,new Rectangle(10,249,601,72),1,true,800,600);
        Check("top_and_bottom",list,new Rectangle(10,19,600,302),1,true,800,600);
        Check("outside_below",list,new Rectangle(10,320,600,72),1,true,800,600);
        Check("visible_minimum",list,new Rectangle(10,284,600,37),1,true,800,600);
        Check("visible_too_short",list,new Rectangle(10,285,600,36),1,true,800,600);
        Check("scaled_minimum",list,new Rectangle(10,266,600,55),1.5,true,800,600);
        Check("scaled_too_short",list,new Rectangle(10,267,600,54),1.5,true,800,600);
        Check("left_misaligned",list,new Rectangle(13,249,597,72),1,true,800,600);
        Check("right_misaligned",list,new Rectangle(10,249,597,72),1,true,800,600);
        Check("narrow",list,new Rectangle(10,249,299,72),1,true,800,600);
        Check("list_outside",list,new Rectangle(10,249,600,72),1,true,800,319);
        Check("missing_image",list,new Rectangle(10,249,600,72),1,false,800,600);
        Check("bad_scale",list,new Rectangle(10,249,600,72),Double.NaN,true,800,600);
        Check("empty_list",Rectangle.Empty,new Rectangle(10,249,600,72),1,true,800,600);
        Check("low_dpi_one",list,new Rectangle(10,249,600,72),.75,true,800,600);
        Check("high_dpi_one",new Rectangle(0,0,900,400),new Rectangle(0,293,900,108),3,true,900,400);
        Check("high_dpi_two",new Rectangle(0,0,900,400),new Rectangle(0,294,900,108),3,true,900,400);
    }
}
