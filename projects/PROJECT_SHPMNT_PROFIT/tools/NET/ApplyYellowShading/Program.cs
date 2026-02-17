using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using DocumentFormat.OpenXml;

if (args.Length == 0) { Console.WriteLine("Usage: dotnet run <file.docx>"); return; }

var docPath = args[0];
Console.WriteLine($"📄 {System.IO.Path.GetFileName(docPath)}");
Console.WriteLine();

// Бэкап
var backup = docPath.Replace(".docx", $"_{DateTime.Now:HHmmss}.bak");
System.IO.File.Copy(docPath, backup, true);
Console.WriteLine($"💾 Бэкап: {System.IO.Path.GetFileName(backup)}");
Console.WriteLine();

var doc = WordprocessingDocument.Open(docPath, true);
var body = doc.MainDocumentPart!.Document.Body!;

int count = 0;

Console.WriteLine("🎨 ПРИМЕНЕНИЕ ЖЕЛТОГО ФОНА:");
Console.WriteLine();

// Найти все параграфы с ⚠️ и применить желтый фон
foreach (var para in body.Descendants<Paragraph>().ToList())
{
    var text = para.InnerText;
    if (text.Contains("⚠️"))
    {
        // Применить желтый фон к параграфу (БЕЗ изменения текста!)
        if (para.ParagraphProperties == null)
        {
            para.ParagraphProperties = new ParagraphProperties();
        }

        var shading = para.ParagraphProperties.GetFirstChild<Shading>();
        if (shading == null)
        {
            shading = new Shading();
            para.ParagraphProperties.AppendChild(shading);
        }

        // Бледно-желтый цвет (как у ⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ)
        shading.Fill = "FFF9C4";  // Светло-желтый
        shading.Val = ShadingPatternValues.Clear;

        count++;
        Console.WriteLine($"  ✅ [{count:2d}] {text.Substring(0, Math.Min(100, text.Length))}...");
    }
}

doc.MainDocumentPart.Document.Save();
doc.Dispose();

Console.WriteLine();
Console.WriteLine(new string('=', 60));
Console.WriteLine($"✅ {count} параграфов получили желтый фон");
Console.WriteLine($"📄 {System.IO.Path.GetFileName(docPath)}");
Console.WriteLine($"💾 {System.IO.Path.GetFileName(backup)}");
Console.WriteLine(new string('=', 60));
