using System.CommandLine;
using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

// HELPERS
int _id = 100000;
int NextId() => Interlocked.Increment(ref _id);

int Replace(WordprocessingDocument doc, string oldText, string newText, bool tracked, string author) {
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

bool AddComment(WordprocessingDocument doc, string search, string text, string author) {
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
    var nextSib = run.NextSibling();
    if (nextSib != null) para.InsertAfter(new Run(new CommentReference { Id = id }), nextSib);
    else para.Append(new Run(new CommentReference { Id = id }));
    commentsPart.Comments.Save();
    mainPart.Document.Save();
    return true;
}

// COMMANDS
var rootCommand = new RootCommand("DOCX Tools");

// REPLACE
var replaceCmd = new Command("replace", "Replace text");
var rFile = new Argument<FileInfo>("file");
var rOld = new Argument<string>("old-text");
var rNew = new Argument<string>("new-text");
var rTracked = new Option<bool>("--tracked");
var rAuthor = new Option<string>("--author", () => "Claude");
var rOutput = new Option<FileInfo?>("--output");
replaceCmd.AddArgument(rFile);
replaceCmd.AddArgument(rOld);
replaceCmd.AddArgument(rNew);
replaceCmd.AddOption(rTracked);
replaceCmd.AddOption(rAuthor);
replaceCmd.AddOption(rOutput);
replaceCmd.SetHandler((file, oldText, newText, tracked, author, output) => {
    var path = output?.FullName ?? file.FullName;
    if (output != null && output.FullName != file.FullName) File.Copy(file.FullName, path, true);
    using var doc = WordprocessingDocument.Open(path, true);
    var count = Replace(doc, oldText, newText, tracked, author);
    doc.MainDocumentPart!.Document.Save();
    Console.WriteLine($"✅ Replaced {count}: '{oldText}' → '{newText}'");
    if (tracked) Console.WriteLine($"   Author: {author}");
}, rFile, rOld, rNew, rTracked, rAuthor, rOutput);

// BATCH
var batchCmd = new Command("batch", "Batch replace from JSON");
var bFile = new Argument<FileInfo>("file");
var bJson = new Argument<FileInfo>("json");
var bTracked = new Option<bool>("--tracked");
var bAuthor = new Option<string>("--author", () => "Claude");
var bOutput = new Option<FileInfo?>("--output");
batchCmd.AddArgument(bFile);
batchCmd.AddArgument(bJson);
batchCmd.AddOption(bTracked);
batchCmd.AddOption(bAuthor);
batchCmd.AddOption(bOutput);
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
}, bFile, bJson, bTracked, bAuthor, bOutput);

// COMMENT
var commentCmd = new Command("comment", "Add comment");
var cFile = new Argument<FileInfo>("file");
var cSearch = new Argument<string>("search");
var cText = new Argument<string>("text");
var cAuthor = new Option<string>("--author", () => "Claude");
commentCmd.AddArgument(cFile);
commentCmd.AddArgument(cSearch);
commentCmd.AddArgument(cText);
commentCmd.AddOption(cAuthor);
commentCmd.SetHandler((file, search, text, author) => {
    using var doc = WordprocessingDocument.Open(file.FullName, true);
    Console.WriteLine(AddComment(doc, search, text, author) 
        ? $"✅ Comment added to '{search}'" 
        : $"❌ Not found: '{search}'");
}, cFile, cSearch, cText, cAuthor);

// INFO
var infoCmd = new Command("info", "Document info");
var iFile = new Argument<FileInfo>("file");
infoCmd.AddArgument(iFile);
infoCmd.SetHandler((file) => {
    using var doc = WordprocessingDocument.Open(file.FullName, false);
    var mp = doc.MainDocumentPart;
    if (mp?.Document?.Body == null) { Console.WriteLine($"❌ Cannot read: {file.Name}"); return; }
    var body = mp.Document.Body;
    var comments = mp.WordprocessingCommentsPart?.Comments?.ChildElements.Count ?? 0;
    Console.WriteLine($"📄 {file.Name} ({file.Length/1024.0:F1} KB)");
    Console.WriteLine($"   Paragraphs: {body.Descendants<Paragraph>().Count()}, Tables: {body.Descendants<Table>().Count()}");
    Console.WriteLine($"   Tracked: {body.Descendants<DeletedRun>().Count()} del, {body.Descendants<InsertedRun>().Count()} ins, {comments} comments");
}, iFile);

// FIND
var findCmd = new Command("find", "Find text");
var fFile = new Argument<FileInfo>("file");
var fText = new Argument<string>("text");
findCmd.AddArgument(fFile);
findCmd.AddArgument(fText);
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
}, fFile, fText);

// ACCEPT
var acceptCmd = new Command("accept", "Accept all changes");
var aFile = new Argument<FileInfo>("file");
var aOutput = new Option<FileInfo?>("--output");
acceptCmd.AddArgument(aFile);
acceptCmd.AddOption(aOutput);
acceptCmd.SetHandler((file, output) => {
    var path = output?.FullName ?? file.FullName;
    if (output != null && output.FullName != file.FullName) File.Copy(file.FullName, path, true);
    using var doc = WordprocessingDocument.Open(path, true);
    var body = doc.MainDocumentPart!.Document.Body!;
    int del = 0, ins = 0;
    foreach (var d in body.Descendants<DeletedRun>().ToList()) { d.Remove(); del++; }
    foreach (var ir in body.Descendants<InsertedRun>().ToList()) {
        var parent = ir.Parent;
        foreach (var c in ir.ChildElements.ToList()) parent?.InsertBefore(c.CloneNode(true), ir);
        ir.Remove(); ins++;
    }
    doc.MainDocumentPart.Document.Save();
    Console.WriteLine($"✅ Accepted: {del} del, {ins} ins");
}, aFile, aOutput);

// REJECT
var rejectCmd = new Command("reject", "Reject all changes");
var rejFile = new Argument<FileInfo>("file");
var rejOutput = new Option<FileInfo?>("--output");
rejectCmd.AddArgument(rejFile);
rejectCmd.AddOption(rejOutput);
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
    foreach (var ir in body.Descendants<InsertedRun>().ToList()) { ir.Remove(); ins++; }
    doc.MainDocumentPart.Document.Save();
    Console.WriteLine($"✅ Rejected: {del} del restored, {ins} ins removed");
}, rejFile, rejOutput);

rootCommand.AddCommand(replaceCmd);
rootCommand.AddCommand(batchCmd);
rootCommand.AddCommand(commentCmd);
rootCommand.AddCommand(infoCmd);
rootCommand.AddCommand(findCmd);
rootCommand.AddCommand(acceptCmd);
rootCommand.AddCommand(rejectCmd);

return await rootCommand.InvokeAsync(args);
