// Conservative visual hints, not sender identity or message identity.
// The caller owns the in-memory bitmap. No image or pixel data is persisted.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Runtime.InteropServices;

public sealed class VisualFrame : IDisposable {
    public Bitmap Image;
    public Rectangle Bounds;
    public double Scale;
    public void Dispose() { if(Image!=null) { Image.Dispose(); Image=null; } }
}

public static class VisualCapture {
    [StructLayout(LayoutKind.Sequential)] struct WinRect { public int Left,Top,Right,Bottom; }
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr window, out WinRect rect);
    [DllImport("user32.dll")] static extern bool PrintWindow(IntPtr window, IntPtr target, uint flags);
    [DllImport("user32.dll")] static extern uint GetDpiForWindow(IntPtr window);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);
    [DllImport("user32.dll")] static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);

    public static void UsePhysicalCoordinates() {
        if(SetThreadDpiAwarenessContext(new IntPtr(-4))==IntPtr.Zero) throw new InvalidOperationException();
    }
    public static VisualFrame Take(IntPtr window) {
        WinRect rect, after;
        if(!IsWindowVisible(window) || IsIconic(window) || !GetWindowRect(window,out rect)) throw new InvalidOperationException();
        long width=(long)rect.Right-rect.Left, height=(long)rect.Bottom-rect.Top;
        double scale=GetDpiForWindow(window)/96.0;
        if(width<1 || height<1 || width>4096 || height>4096 || width*height>8000000 || scale<0.75 || scale>3)
            throw new InvalidOperationException();
        var frame=new VisualFrame {Image=new Bitmap((int)width,(int)height),
            Bounds=new Rectangle(rect.Left,rect.Top,(int)width,(int)height),Scale=scale};
        try {
            using(var graphics=Graphics.FromImage(frame.Image)) {
                graphics.Clear(Color.Black);
                IntPtr hdc=graphics.GetHdc();
                // PW_RENDERFULLCONTENT (Windows SDK): Qt otherwise returned
                // a successful but empty message area in the live check.
                try { if(!PrintWindow(window,hdc,2)) throw new InvalidOperationException(); }
                finally { graphics.ReleaseHdc(hdc); }
            }
            if(!IsWindowVisible(window) || IsIconic(window) || !GetWindowRect(window,out after)
                    || rect.Left!=after.Left || rect.Top!=after.Top || rect.Right!=after.Right || rect.Bottom!=after.Bottom
                    || GetDpiForWindow(window)/96.0!=scale) throw new InvalidOperationException();
            return frame;
        } catch { frame.Dispose(); throw; }
    }
}

public sealed class VisualClassification {
    public readonly string Direction, Reason, GeometryReason;
    public VisualClassification(string direction, string reason) : this(direction,reason,null) { }
    public VisualClassification(string direction, string reason, string geometryReason) {
        Direction=direction; Reason=reason; GeometryReason=geometryReason;
    }
}

public static class VisualRetry {
    public static bool ShouldRetry(IList<VisualClassification> rows, int attempts) {
        if(attempts<1 || attempts>=3) return false;
        bool absent=false;
        foreach(var row in rows) {
            if(row.Reason=="foreground_evidence_absent") absent=true;
            else if(row.Reason!="geometry_invalid" && row.Reason!="not_text") return false;
        }
        return absent;
    }
}

public static class VisualDirection {
    static int Distance(Color a, Color b) {
        return Math.Max(Math.Abs(a.R-b.R),Math.Max(Math.Abs(a.G-b.G),Math.Abs(a.B-b.B)));
    }
    static bool Neutral(Color c) {
        return Math.Max(c.R,Math.Max(c.G,c.B))-Math.Min(c.R,Math.Min(c.G,c.B))<=6;
    }
    static bool Green(Color c) { return c.G>100 && c.G>c.R+30 && c.G>c.B+30; }
    static int Count(Bitmap image, Rectangle row, double scale, int from, int to, Color background, int mode) {
        int count=0, left=row.Left+(int)Math.Round(from*scale), right=row.Left+(int)Math.Round(to*scale);
        int bottom=Math.Min(row.Bottom,row.Top+(int)Math.Round(64*scale));
        for(int y=row.Top; y<bottom; y+=2)
            for(int x=left; x<right; x+=2) {
                Color c=image.GetPixel(x,y);
                int distance=Distance(c,background);
                if (mode==0 ? distance>=10 : mode==1 ? Neutral(c) && distance>=6 && distance<=90 : Green(c)) count++;
            }
        return count;
    }
    public static string Classify(Bitmap image, Rectangle list, Rectangle row, double scale) {
        return Analyze(image,list,row,scale).Direction;
    }
    // Same gates and order as classification; only fixed failure names escape.
    // Scalar/rectangle inputs also allow checking these gates without a bitmap.
    public static string GeometryFailure(bool hasImage, int imageWidth, int imageHeight,
                                         Rectangle list, Rectangle row, double scale) {
        if(!hasImage) return "image_missing";
        if(Double.IsNaN(scale) || Double.IsInfinity(scale) || scale<0.75 || scale>3) return "scale_invalid";
        if(list.Width<=0 || list.Height<=0) return "list_size_invalid";
        if(row.Width<300*scale) return "row_width_below_minimum";
        if(row.Height<36*scale) return "row_height_below_minimum";
        if(!new Rectangle(0,0,imageWidth,imageHeight).Contains(list)) return "list_outside_frame";
        if(!list.Contains(row)) return "row_outside_list";
        if(Math.Abs(row.Left-list.Left)>2*scale) return "row_left_misaligned";
        if(Math.Abs(row.Right-list.Right)>2*scale) return "row_right_misaligned";
        return null;
    }
    // The observed UIA row can include one physical pixel below the list.
    // Exclude that pixel from every sample; never read past the list, shift
    // the row's origin, accept other clipping, or waive the original gates.
    public static string AnalysisGeometry(bool hasImage, int imageWidth, int imageHeight,
                                         Rectangle list, Rectangle row, double scale,
                                         out Rectangle analysisRow) {
        analysisRow=Rectangle.Empty;
        string failure=GeometryFailure(hasImage,imageWidth,imageHeight,list,row,scale);
        if(failure=="row_outside_list" && row.Top>=list.Top && row.Left>=list.Left
                && row.Right<=list.Right && (long)row.Bottom-list.Bottom==1) {
            row=new Rectangle(row.X,row.Y,row.Width,row.Height-1);
            failure=GeometryFailure(hasImage,imageWidth,imageHeight,list,row,scale);
        }
        if(failure==null) analysisRow=row;
        return failure;
    }
    // Reasons name the first unmet gate, not a proven capture/rendering cause.
    public static VisualClassification Analyze(Bitmap image, Rectangle list, Rectangle row, double scale) {
        Rectangle analysisRow;
        string geometryReason=AnalysisGeometry(image!=null,image==null ? 0 : image.Width,
            image==null ? 0 : image.Height,list,row,scale,out analysisRow);
        if(geometryReason!=null) return new VisualClassification("unknown","geometry_invalid",geometryReason);
        row=analysisRow;
        int left=row.Left+(int)Math.Round(8*scale), right=row.Right-(int)Math.Round(8*scale)-1;
        Color background=image.GetPixel(left,row.Top+row.Height/2);
        if(!Neutral(background) || !(background.R>=235 || (background.R>=20 && background.R<=45)))
            return new VisualClassification("unknown","background_unsupported");
        int matches=0, samples=0;
        for(int y=row.Top; y<row.Bottom; y+=3) {
            samples+=2;
            if(Distance(image.GetPixel(left,y),background)<=4) matches++;
            if(Distance(image.GetPixel(right,y),background)<=4) matches++;
        }
        if(matches<samples*0.95) return new VisualClassification("unknown","edges_inconsistent");
        // Require an avatar on exactly one side AND a compatible bubble there.
        // A missing green bubble alone must never imply an incoming message.
        int width=(int)Math.Round(row.Width/scale);
        double threshold=30*scale*scale, empty=5*scale*scale;
        int leftAvatar=Count(image,row,scale,14,62,background,0);
        int rightAvatar=Count(image,row,scale,width-62,width-14,background,0);
        if(leftAvatar>=threshold && rightAvatar<=empty) {
            if(Count(image,row,scale,64,165,background,1)<threshold)
                return new VisualClassification("unknown","incoming_bubble_unconfirmed");
            if(Count(image,row,scale,64,165,background,2)>empty)
                return new VisualClassification("unknown","incoming_green_conflict");
            return new VisualClassification("incoming_candidate","incoming_evidence");
        }
        if(rightAvatar>=threshold && leftAvatar<=empty) {
            if(Count(image,row,scale,width-165,width-64,background,2)<threshold)
                return new VisualClassification("unknown","self_bubble_unconfirmed");
            return new VisualClassification("self_candidate","self_evidence");
        }
        if(leftAvatar==0 && rightAvatar==0
                && Count(image,row,scale,64,165,background,1)==0
                && Count(image,row,scale,64,165,background,2)==0
                && Count(image,row,scale,width-165,width-64,background,2)==0)
            return new VisualClassification("unknown","foreground_evidence_absent");
        return new VisualClassification("unknown","avatar_inconclusive");
    }
}
