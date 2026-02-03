#!/bin/bash
# setup.sh — Установка DOCX Tools
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔧 DOCX Tools Setup"
echo "   Dir: $SCRIPT_DIR"

# 1. Проверяем .NET
echo ""
echo "1. Checking .NET SDK..."
if command -v dotnet &> /dev/null; then
    echo "   ✅ .NET $(dotnet --version)"
else
    echo "   Installing .NET..."
    brew install dotnet
fi

# 2. Создаём .csproj
echo ""
echo "2. Creating project..."
cat > DocxTools.csproj << 'CSPROJ'
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="DocumentFormat.OpenXml" Version="3.0.2" />
    <PackageReference Include="System.CommandLine" Version="2.0.0-beta4.22272.1" />
  </ItemGroup>
</Project>
CSPROJ
echo "   ✅ DocxTools.csproj"

# 3. Создаём Program.cs
echo ""
echo "3. Creating source..."
cat > Program.cs << 'PROGRAMCS'
using System.CommandLine;
using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

var rootCommand = new RootCommand("DOCX Tools");

// REPLACE
var replaceCmd = new Command("replace", "Replace text");
replaceCmd.AddArgument(new Argument<FileInfo>("file"));
replaceCmd.AddArgument(new Argument<string>("old-text"));
replaceCmd.AddArgument(new Argument<string>("new-text"));
replaceCmd.AddOption(new Option<bool>("--tracked"));
replaceCmd.AddOption(new Option<string>("--author", () => "Claude"));
replaceCmd.AddOption(new Option<FileInfo?>("--output"));
replaceCmd.SetHandler((file, oldText, newText, tracked, author, output) => {
    var path = output?.FullName ?? file.FullName;
    if (output != null && output.FullName != file.FullName) File.Copy(file.FullName, path, true);
    using var doc = WordprocessingDocument.Open(path, true);
    var count = Replace(doc, oldText, newText, tracked, author);
    doc.MainDocumentPart!.Document.Save();
    Console.WriteLine($"✅ Replaced {count}: '{oldText}' → '{newText}'");
    if (tracked) Console.WriteLine($"   Author: {author}");
}, new Argument<FileInfo>("file"), new Argument<string>("old-text"), new Argument<string>("new-text"),
   new Option<bool>("--tracked"), new Option<string>("--author", () => "Claude"), new Option<FileInfo?>("--output"));

// BATCH
var batchCmd = new Command("batch", "Batch replace from JSON");
batchCmd.AddArgument(new Argument<FileInfo>("file"));
batchCmd.AddArgument(new Argument<FileInfo>("json"));
batchCmd.AddOption(new Option<bool>("--tracked"));
batchCmd.AddOption(new Option<string>("--author", () => "Claude"));
batchCmd.AddOption(new Option<FileInfo?>("--output"));
batchCmd.SetHandler((file, json, tracked, author, output) => {
    var path = output?.FullName ?? file.FullName;
    if (output != null && output.FullName != file.FullName) File.Copy(file.FullName, path, true);
    var replacements = JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(json.FullName))!;
    Console.WriteLine($"📄 {file.Name} | 📋 {replacements.Count} replacements");
    using var doc = WordprocessingDocument.Open(path, true);
    int total = 0;
    foreach (var (o, n) in replacements) {
        var c = Replace(doc, o, n, tracked, author);
        Console.WriteLine(c > 0 ? $"  ✓ '{o}' → '{n}': {c}" : $"  ⚠ '{o}': not found");
        total += c;
    }
    doc.MainDocumentPart!.Document.Save();
    Console.WriteLine($"✅ Total: {total} replacements" + (tracked ? $" (by {author})" : ""));
}, new Argument<FileInfo>("file"), new Argument<FileInfo>("json"), new Option<bool>("--tracked"),
   new Option<string>("--author", () => "Claude"), new Option<FileInfo?>("--output"));

// COMMENT
var commentCmd = new Command("comment", "Add comment");
commentCmd.AddArgument(new Argument<FileInfo>("file"));
commentCmd.AddArgument(new Argument<string>("search"));
commentCmd.AddArgument(new Argument<string>("text"));
commentCmd.AddOption(new Option<string>("--author", () => "Claude"));
commentCmd.SetHandler((file, search, text, author) => {
    using var doc = WordprocessingDocument.Open(file.FullName, true);
    Console.WriteLine(AddComment(doc, search, text, author) 
        ? $"✅ Comment added to '{search}'" 
        : $"❌ Not found: '{search}'");
}, new Argument<FileInfo>("file"), new Argument<string>("search"), new Argument<string>("text"),
   new Option<string>("--author", () => "Claude"));

// INFO
var infoCmd = new Command("info", "Document info");
infoCmd.AddArgument(new Argument<FileInfo>("file"));
infoCmd.SetHandler((file) => {
    using var doc = WordprocessingDocument.Open(file.FullName, false);
    var body = doc.MainDocumentPart!.Document.Body!;
    var mp = doc.MainDocumentPart;
    Console.WriteLine($"📄 {file.Name} ({file.Length/1024.0:F1} KB)");
    Console.WriteLine($"   Paragraphs: {body.Descendants<Paragraph>().Count()}, Tables: {body.Descendants<Table>().Count()}");
    Console.WriteLine($"   Tracked: {body.Descendants<DeletedRun>().Count()} del, {body.Descendants<InsertedRun>().Count()} ins, {mp.WordprocessingCommentsPart?.Comments?.Count() ?? 0} comments");
}, new Argument<FileInfo>("file"));

// FIND
var findCmd = new Command("find", "Find text");
findCmd.AddArgument(new Argument<FileInfo>("file"));
findCmd.AddArgument(new Argument<string>("text"));
findCmd.SetHandler((file, text) => {
    using var doc = WordprocessingDocument.Open(file.FullName, false);
    int i = 0, found = 0;
    foreach (var p in doc.MainDocumentPart!.Document.Body!.Descendants<Paragraph>()) {
        i++;
        var pt = p.InnerText;
        if (pt.Contains(text, StringComparison.OrdinalIgnoreCase)) {
            found++;
            var idx = pt.IndexOf(text, StringComparison.OrdinalIgnoreCase);
            Console.WriteLine($"  [{i}] ...{pt[Math.Max(0,idx-40)..Math.Min(pt.Length,idx+text.Length+40)]}...");
        }
    }
    Console.WriteLine($"✅ Found in {found} paragraphs");
}, new Argument<FileInfo>("file"), new Argument<string>("text"));

// ACCEPT
var acceptCmd = new Command("accept", "Accept all changes");
acceptCmd.AddArgument(new Argument<FileInfo>("file"));
acceptCmd.AddOption(new Option<FileInfo?>("--output"));
acceptCmd.SetHandler((file, output) => {
    var path = output?.FullName ?? file.FullName;
    if (output != null && output.FullName != file.FullName) File.Copy(file.FullName, path, true);
    using var doc = WordprocessingDocument.Open(path, true);
    var body = doc.MainDocumentPart!.Document.Body!;
    int del = 0, ins = 0;
    foreach (var d in body.Descendants<DeletedRun>().ToList()) { d.Remove(); del++; }
    foreach (var i in body.Descendants<InsertedRun>().ToList()) {
        var parent = i.Parent;
        foreach (var c in i.ChildElements.ToList()) parent?.InsertBefore(c.CloneNode(true), i);
        i.Remove(); ins++;
    }
    doc.MainDocumentPart.Document.Save();
    Console.WriteLine($"✅ Accepted: {del} del, {ins} ins");
}, new Argument<FileInfo>("file"), new Option<FileInfo?>("--output"));

// REJECT
var rejectCmd = new Command("reject", "Reject all changes");
rejectCmd.AddArgument(new Argument<FileInfo>("file"));
rejectCmd.AddOption(new Option<FileInfo?>("--output"));
rejectCmd.SetHandler((file, output) => {
    var path = output?.FullName ?? file.FullName;
    if (output != null && output.FullName != file.FullName) File.Copy(file.FullName, path, true);
    using var doc = WordprocessingDocument.Open(path, true);
    var body = doc.MainDocumentPart!.Document.Body!;
    int del = 0, ins = 0;
    foreach (var d in body.Descendants<DeletedRun>().ToList()) {
        var parent = d.Parent;
        foreach (var run in d.Descendants<Run>()) {
            var newRun = new Run();
            if (run.RunProperties != null) newRun.RunProperties = run.RunProperties.CloneNode(true) as RunProperties;
            foreach (var dt in run.Descendants<DeletedText>())
                newRun.Append(new Text { Text = dt.Text, Space = SpaceProcessingModeValues.Preserve });
            parent?.InsertBefore(newRun, d);
        }
        d.Remove(); del++;
    }
    foreach (var i in body.Descendants<InsertedRun>().ToList()) { i.Remove(); ins++; }
    doc.MainDocumentPart.Document.Save();
    Console.WriteLine($"✅ Rejected: {del} del restored, {ins} ins removed");
}, new Argument<FileInfo>("file"), new Option<FileInfo?>("--output"));

rootCommand.AddCommand(replaceCmd);
rootCommand.AddCommand(batchCmd);
rootCommand.AddCommand(commentCmd);
rootCommand.AddCommand(infoCmd);
rootCommand.AddCommand(findCmd);
rootCommand.AddCommand(acceptCmd);
rootCommand.AddCommand(rejectCmd);

return await rootCommand.InvokeAsync(args);

// HELPERS
static int _id = 100000;
static int NextId() => Interlocked.Increment(ref _id);

static int Replace(WordprocessingDocument doc, string oldText, string newText, bool tracked, string author) {
    var body = doc.MainDocumentPart!.Document.Body!;
    var date = DateTime.UtcNow;
    int count = 0;
    foreach (var t in body.Descendants<Text>().ToList()) {
        if (!t.Text.Contains(oldText)) continue;
        if (tracked) {
            var run = t.Parent as Run; var parent = run?.Parent;
            if (parent == null) continue;
            var rPr = run!.RunProperties?.CloneNode(true) as RunProperties;
            var del = new DeletedRun { Author = author, Date = date, Id = NextId().ToString() };
            var delRun = new Run();
            if (rPr != null) delRun.RunProperties = rPr.CloneNode(true) as RunProperties;
            delRun.Append(new DeletedText { Text = t.Text, Space = SpaceProcessingModeValues.Preserve });
            del.Append(delRun);
            var ins = new InsertedRun { Author = author, Date = date, Id = NextId().ToString() };
            var insRun = new Run();
            if (rPr != null) insRun.RunProperties = rPr.CloneNode(true) as RunProperties;
            insRun.Append(new Text { Text = t.Text.Replace(oldText, newText), Space = SpaceProcessingModeValues.Preserve });
            ins.Append(insRun);
            parent.InsertBefore(del, run); parent.InsertBefore(ins, run); run.Remove();
        } else { t.Text = t.Text.Replace(oldText, newText); }
        count++;
    }
    return count;
}

static bool AddComment(WordprocessingDocument doc, string search, string text, string author) {
    var mainPart = doc.MainDocumentPart!;
    var body = mainPart.Document.Body!;
    var commentsPart = mainPart.WordprocessingCommentsPart ?? mainPart.AddNewPart<WordprocessingCommentsPart>();
    if (commentsPart.Comments == null) commentsPart.Comments = new Comments();
    var textEl = body.Descendants<Text>().FirstOrDefault(t => t.Text.Contains(search));
    if (textEl == null) return false;
    var run = textEl.Parent as Run; var para = run?.Parent as Paragraph;
    if (para == null) return false;
    var id = NextId().ToString();
    var comment = new Comment { Id = id, Author = author, Date = DateTime.UtcNow };
    comment.Append(new Paragraph(new Run(new Text(text))));
    commentsPart.Comments.Append(comment);
    para.InsertBefore(new CommentRangeStart { Id = id }, run);
    para.InsertAfter(new CommentRangeEnd { Id = id }, run);
    para.InsertAfter(new Run(new CommentReference { Id = id }), run.NextSibling());
    commentsPart.Comments.Save();
    mainPart.Document.Save();
    return true;
}
PROGRAMCS
echo "   ✅ Program.cs"

# 4. Сборка
echo ""
echo "4. Building..."
dotnet restore -v q
dotnet build -c Release -v q
echo "   ✅ Build OK"

echo ""
echo "========================================="
echo "✅ DOCX Tools ready!"
echo ""
echo "Usage (from fm-review-system root):"
echo "  dotnet run --project PROJECT_SHPMNT_PROFIT/tools/NET -- info FILE.docx"
echo "  dotnet run --project PROJECT_SHPMNT_PROFIT/tools/NET -- replace FILE.docx \"old\" \"new\" --tracked"
echo "========================================="
