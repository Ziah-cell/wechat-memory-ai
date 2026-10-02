using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using System.Windows;

public static class VisualRowFixture {
    public static int Main() {
        var bounds=new Rect(10,20,600,72);
        var before=new VisualRow("1","text","fixture",bounds);
        var results=new Dictionary<string,bool> {
            {"same",before.Matches(new VisualRow("1","text","fixture",bounds))},
            {"text",before.Matches(new VisualRow("1","text","changed",bounds))},
            {"token",before.Matches(new VisualRow("2","text","fixture",bounds))},
            {"kind",before.Matches(new VisualRow("1","other","fixture",bounds))},
            {"bounds",before.Matches(new VisualRow("1","text","fixture",new Rect(10,21,600,72)))},
            {"missing",before.Matches(null)},
            {"diagnostic",new VisualRow("1","text",null,bounds).Matches(new VisualRow("1","text",null,bounds))}
        };
        Console.WriteLine(new JavaScriptSerializer().Serialize(results));
        return 0;
    }
}
