using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using System.Windows.Forms;

class FakeVisualWindow : Form {
    protected override bool ShowWithoutActivation { get { return true; } }
    protected override void OnPaint(PaintEventArgs e) {
        base.OnPaint(e);
        e.Graphics.FillRectangle(Brushes.DarkOliveGreen,20,12,36,36);
        using(var bubble=new SolidBrush(Color.FromArgb(237,237,237)))
            e.Graphics.FillRectangle(bubble,70,12,190,36);
    }
}
class CaptureFixture {
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [STAThread] static void Main() {
        SetProcessDPIAware();
        using(var window=new FakeVisualWindow()) {
            window.FormBorderStyle=FormBorderStyle.None;
            window.StartPosition=FormStartPosition.Manual;
            var desktop=Screen.PrimaryScreen.WorkingArea;
            window.Location=new Point(desktop.Right-610,desktop.Bottom-82);
            window.Size=new Size(600,72);
            window.BackColor=Color.FromArgb(250,250,250);
            window.ShowInTaskbar=false;
            window.Show();
            window.Refresh();
            // PW_RENDERFULLCONTENT uses the compositor. Give our synthetic
            // non-activating window one render cycle before taking its image.
            Application.DoEvents();
            System.Threading.Thread.Sleep(100);
            using(var frame=VisualCapture.Take(window.Handle)) {
                var rect=new Rectangle(0,0,frame.Image.Width,frame.Image.Height);
                Console.WriteLine(new JavaScriptSerializer().Serialize(new {
                    direction=VisualDirection.Classify(frame.Image,rect,rect,1),
                    width=frame.Image.Width,height=frame.Image.Height}));
            }
        }
    }
}
