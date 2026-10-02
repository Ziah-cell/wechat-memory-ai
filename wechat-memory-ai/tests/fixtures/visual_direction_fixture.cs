// Synthetic bitmaps only; never opens or captures a real window.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Web.Script.Serialization;

class VisualFixture {
    static void Fill(Graphics g, Color color, double scale, int x, int y, int w, int h) {
        using (var brush=new SolidBrush(color))
            g.FillRectangle(brush,(int)(x*scale),(int)(y*scale),(int)(w*scale),(int)(h*scale));
    }
    static string Case(string name, double scale) {
        int width=(int)(600*scale), height=(int)(72*scale);
        using(var bitmap=new Bitmap(width,height)) {
            bool dark=name.StartsWith("dark");
            Color background=dark ? Color.FromArgb(30,30,31) : Color.FromArgb(250,250,250);
            using(var g=Graphics.FromImage(bitmap)) {
                g.Clear(name=="black" ? Color.Black : background);
                bool incoming=name.Contains("incoming") || name=="both" || name=="clipped";
                bool self=name.Contains("self") || name=="both";
                if (incoming) {
                    Fill(g,Color.FromArgb(90,115,70),scale,20,12,36,36);
                    Fill(g,dark ? Color.FromArgb(50,50,51) : Color.FromArgb(237,237,237),scale,70,12,190,36);
                }
                if (self) {
                    Fill(g,Color.FromArgb(100,80,120),scale,544,12,36,36);
                    Fill(g,Color.FromArgb(149,236,108),scale,330,12,198,36);
                }
                if (name=="green_without_avatar") Fill(g,Color.FromArgb(149,236,108),scale,330,12,198,36);
                if (name=="avatar_without_bubble") Fill(g,Color.FromArgb(90,115,70),scale,20,12,36,36);
                if (name=="incoming_green_bubble") Fill(g,Color.FromArgb(149,236,108),scale,70,12,190,36);
                if (name=="self_gray_bubble") Fill(g,Color.FromArgb(237,237,237),scale,330,12,198,36);
                if (name=="noise") {
                    Fill(g,Color.FromArgb(90,115,70),scale,20,12,3,3);
                    Fill(g,Color.FromArgb(149,236,108),scale,470,12,3,3);
                }
            }
            Rectangle list=new Rectangle(0,0,width,height);
            Rectangle row=list;
            if (name=="clipped") row.Y=-10;
            if (name=="too_narrow") row.Width=100;
            return VisualDirection.Classify(bitmap,list,row,scale);
        }
    }
    static void Main() {
        var results=new Dictionary<string,string>();
        foreach(string name in new[]{"incoming","self","dark_incoming","dark_self","both","blank","black",
                "clipped","too_narrow","green_without_avatar","avatar_without_bubble",
                "incoming_green_bubble","self_gray_bubble","noise"}) results[name]=Case(name,1);
        results["scaled_incoming"]=Case("incoming",1.5);
        results["scaled_self"]=Case("self",2);
        using(var bitmap=new Bitmap(600,72)) {
            results["invalid_scale"]=VisualDirection.Classify(bitmap,new Rectangle(0,0,600,72),new Rectangle(0,0,600,72),Double.NaN);
            results["outside_image"]=VisualDirection.Classify(bitmap,new Rectangle(0,0,800,72),new Rectangle(0,0,600,72),1);
        }
        Console.WriteLine(new JavaScriptSerializer().Serialize(results));
    }
}
