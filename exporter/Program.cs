// ChorusExport: reads Chorus (UE 4.26, pak v11, encrypted index, Zlib) with CUE4Parse; part of chorus_ships_importer.
// Environment: CHORUS_GAME (the install folder), CHORUS_AES_KEY (0x...; `keyscan` finds it in your own exe), CHORUS_USMAP (optional:
// Chorus packages carry their property types, so no mappings file is needed).
//   keyscan                   the pak key from the game exe        list [regex]   package paths
//   json <path> <out.json>    one package as JSON                  jsonall <regex> <dir>   every match
//   export <list> <outdir>    meshes as .glb + materials (.json) + textures (.png), in FModel's layout
//   shaders <material> <outdir>  a material's compiled shaders (DXBC, from the shader library) and its uniforms.json
//   raw <regex> <outdir>      the files matching, as they are in the pak (.locres text tables, ...)
using Serilog;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Assets.Exports.Material;

Log.Logger = new LoggerConfiguration().MinimumLevel.Warning().WriteTo.Console().CreateLogger();
string Env(string n) => Environment.GetEnvironmentVariable(n) ?? throw new Exception("set " + n);
if (args.Length > 0 && args[0] == "keyscan")
{
    // keyscan: the pak's AES-256 key from the shipping exe (UE_REGISTER_ENCRYPTION_KEY compiles it to eight imm32 moves):
    // every run of 8 nearby `mov [reg+d], imm32` is tried on the encrypted index's first block, which must decrypt to a
    // mount-point FString ("../../../"). Prints 0x<key>. Same method as the ES2 tools' ShaderDump keyscan.
    var gameDir = Env("CHORUS_GAME");
    var exePath = Directory.GetFiles(gameDir, "*-Shipping.exe", SearchOption.AllDirectories).OrderByDescending(f => new FileInfo(f).Length).First();   // the real one, not the root launcher stub
    var pakPath = Directory.GetFiles(gameDir, "*.pak", SearchOption.AllDirectories).OrderByDescending(f => new FileInfo(f).Length).First();
    var pak = new CUE4Parse.UE4.Pak.PakFileReader(pakPath, new VersionContainer(EGame.GAME_UE4_26));
    var blk = new byte[16];
    using (var fs = File.OpenRead(pakPath)) { fs.Seek(pak.Info.IndexOffset, SeekOrigin.Begin); fs.ReadExactly(blk); }
    var exe = File.ReadAllBytes(exePath);
    var aes = System.Security.Cryptography.Aes.Create(); var outb = new byte[16];
    var imms = new List<(int pos, uint v)>();
    for (int i = 0; i + 12 < exe.Length; i++)
    {
        if (exe[i] != 0xC7) continue;
        int len = exe[i + 1] switch { 0x45 => 3, 0x44 when exe[i + 2] == 0x24 => 4, 0x85 => 6, 0x84 when exe[i + 2] == 0x24 => 7, 0x40 or 0x41 or 0x42 or 0x43 or 0x46 or 0x47 => 3, 0x00 or 0x01 or 0x02 or 0x03 or 0x06 or 0x07 => 2, _ => 0 };   // [reg+d8] and plain [reg] (Chorus: c7 01 for the first dword)
        if (len > 0) imms.Add((i, BitConverter.ToUInt32(exe, i + len)));
    }
    var key = new byte[32];
    for (int a = 0; a + 8 <= imms.Count; a++)
    {
        if (imms[a + 7].pos - imms[a].pos > 200) continue;
        for (int j = 0; j < 8; j++) BitConverter.GetBytes(imms[a + j].v).CopyTo(key, j * 4);
        aes.Key = key; aes.DecryptEcb(blk, outb, System.Security.Cryptography.PaddingMode.None);
        int sl = BitConverter.ToInt32(outb, 0);
        if (sl > 0 && sl < 512 && outb[4] == '.' && outb[5] == '.' && outb[6] == '/') { Console.WriteLine("0x" + Convert.ToHexString(key)); return; }
    }
    Console.Error.WriteLine($"key not found ({imms.Count} imm32 moves tried)"); Environment.Exit(1);
}
var provider = new DefaultFileProvider(Env("CHORUS_GAME"), SearchOption.AllDirectories, new VersionContainer(EGame.GAME_UE4_26), StringComparer.OrdinalIgnoreCase);
var usmap = Environment.GetEnvironmentVariable("CHORUS_USMAP");
if (!string.IsNullOrEmpty(usmap)) provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmap);
if (args.Length > 0 && args[0] == "shaders") provider.ReadShaderMaps = true;
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey(Env("CHORUS_AES_KEY")));
provider.PostMount();
Console.Error.WriteLine($"mounted {provider.MountedVfs.Count}, locked {provider.UnloadedVfs.Count}, files {provider.Files.Count}");
string Norm(string p) => p.StartsWith("/Game/") ? "SpacePrototype/Content/" + p.Substring(6) : p;
switch (args[0])
{
    case "list":
        var rx = new System.Text.RegularExpressions.Regex(args.Length > 1 ? args[1] : ".", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        foreach (var f in provider.Files.Keys) if (rx.IsMatch(f)) Console.WriteLine(f);
        break;
    case "fmod":
    {
        // fmod <event regex> <outdir>: Chorus's FMOD Studio events (their paths from MasterBank.strings.bank) -> the waves
        // their timelines play (CUE4Parse's EventNodesResolver), decoded (Fmod5Sharp) into <outdir>/<event>/<wave>.<ext>,
        // with <outdir>/events.json listing them. The banks are the loose ones in the install's FMOD/Desktop; one is read
        // at a time. CHORUS_FMOD_SKIP (regex, default ambience / voice / music) leaves banks out.
        var want = new System.Text.RegularExpressions.Regex(args[1], System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        var skip = new System.Text.RegularExpressions.Regex(Environment.GetEnvironmentVariable("CHORUS_FMOD_SKIP") ?? "^(Amb_|Voice_|Mus|Cutscenes_|Debug)",
                                                            System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        var fmodDir = Directory.GetDirectories(Env("CHORUS_GAME"), "Desktop", SearchOption.AllDirectories)
            .First(d => d.Replace('\\', '/').Contains("/FMOD/"));
        CUE4Parse.UE4.FMod.FModReader OpenBank(string f) =>
            new CUE4Parse.UE4.FMod.FModReader(new BinaryReader(new MemoryStream(File.ReadAllBytes(f))), Path.GetFileNameWithoutExtension(f));
        var names = new Dictionary<CUE4Parse.UE4.FMod.Objects.FModGuid, string>();
        var tree = OpenBank(Path.Combine(fmodDir, "MasterBank.strings.bank")).StringTable?.RadixTree
                   ?? throw new InvalidOperationException("MasterBank.strings.bank has no string table");
        for (int i = 0; i < tree.Guids.Length; i++)
            if (tree.TryGetStringByIndex(i, out var path) && path.StartsWith("event:/") && want.IsMatch(path)) names[tree.Guids[i]] = path;
        Console.Error.WriteLine($"{names.Count} events match");
        if (args[2] == "-") { foreach (var n in names.Values.OrderBy(n => n)) Console.WriteLine(n); break; }   // list only
        Directory.CreateDirectory(args[2]);
        var manifest = new SortedDictionary<string, object>();
        foreach (var bankFile in Directory.GetFiles(fmodDir, "*.bank").OrderBy(f => f))
        {
            var bankName = Path.GetFileNameWithoutExtension(bankFile);
            if (bankName.EndsWith(".strings") || skip.IsMatch(bankName)) continue;
            CUE4Parse.UE4.FMod.FModReader bank;
            try { bank = OpenBank(bankFile); } catch (Exception e) { Console.Error.WriteLine($"{bankName}: {e.Message}"); continue; }
            if (!bank.EventNodes.Keys.Any(names.ContainsKey)) continue;
            var resolved = CUE4Parse.UE4.FMod.Utils.EventNodesResolver.TryResolveAudioEvents(bank, out _);
            foreach (var (guid, samples) in resolved)
            {
                if (!names.TryGetValue(guid, out var path)) continue;
                var dir = Path.Combine(args[2], path.Substring("event:/".Length).Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(dir);
                var files = new List<string>();
                foreach (var sample in samples)
                {
                    if (!sample.RebuildAsStandardFileFormat(out var data, out var ext) || data == null) continue;
                    var file = Path.Combine(dir, (sample.Name ?? "sample") + "." + ext.ToLowerInvariant());
                    File.WriteAllBytes(file, data);
                    files.Add(Path.GetRelativePath(args[2], file).Replace('\\', '/'));
                }
                manifest[path] = new { bank = bankName, waves = files };
            }
        }
        File.WriteAllText(Path.Combine(args[2], "events.json"), Newtonsoft.Json.JsonConvert.SerializeObject(manifest, Newtonsoft.Json.Formatting.Indented));
        Console.WriteLine($"{manifest.Count} events -> {args[2]}");
        break;
    }
    case "shaders":
    {
        // shaders <material path> <outdir>: the material's shader map (the first of its parent chain that has one): every
        // shader type per vertex factory (shadermap.txt), the uniform buffer's layout and preshaders (uniforms.json: which
        // parameter fills which slot), and each shader's code out of the project's shader library (LZ4-decompressed; a
        // DXBC container, for d3dcompiler's disassembler) as <index>_<frequency>.bin
        Directory.CreateDirectory(args[2]);
        UMaterialInterface? mat = provider.LoadPackageObject<UMaterialInterface>(Norm(args[1]));
        var log = new System.Text.StringBuilder();
        CUE4Parse.UE4.Assets.Exports.Material.FMaterialShaderMap? sm = null;
        for (var p = mat; p != null; p = (p as UMaterialInstance)?.Parent?.Load<UMaterialInterface>())
        {
            log.AppendLine($"{p.GetPathName()}: {p.LoadedMaterialResources?.Count ?? 0} resources");
            sm = p.LoadedMaterialResources?.Select(r => r.LoadedShaderMap).FirstOrDefault(x => x != null);
            if (sm != null) break;
        }
        if (sm == null) { Console.Error.WriteLine("no shader map in the chain"); File.WriteAllText(Path.Combine(args[2], "shadermap.txt"), log.ToString()); break; }
        log.AppendLine($"platform {sm.ShaderPlatform} hash {sm.ResourceHash}");
        void ListC(string label, FShaderMapContent c) { foreach (var x in c.Shaders) log.AppendLine($"  [{label}] {x.Type} freq {x.Target.Frequency} res {x.ResourceIndex} instr {x.NumInstructions}"); }
        if (sm.Content != null) ListC("material", sm.Content);
        if (sm.Content is FMaterialShaderMapContent mc)
        {
            File.WriteAllText(Path.Combine(args[2], "uniforms.json"), Newtonsoft.Json.JsonConvert.SerializeObject(mc.MaterialCompilationOutput, Newtonsoft.Json.Formatting.Indented));
            if (mc.OrderedMeshShaderMaps != null) foreach (var vf in mc.OrderedMeshShaderMaps) ListC(vf.VertexFactoryTypeName.ToString(), vf);
        }
        var libPath = provider.Files.Keys.First(k => k.EndsWith("ShaderArchive-SpacePrototype-PCD3D_SM5.ushaderbytecode", StringComparison.OrdinalIgnoreCase));
        var lib = new CUE4Parse.UE4.Shaders.FShaderCodeArchive(new CUE4Parse.UE4.Readers.FByteArchive("lib", provider.Files[libPath].Read(), provider.Versions));
        var a = (CUE4Parse.UE4.Shaders.FSerializedShaderArchive) lib.SerializedShaders;
        int mi = Array.FindIndex(a.ShaderMapHashes, h => h.ToString() == sm.ResourceHash?.ToString());
        log.AppendLine($"library: {a.ShaderMapHashes.Length} maps, {a.ShaderEntries.Length} shaders; ours {mi}");
        if (mi >= 0)
        {
            var me = a.ShaderMapEntries[mi];
            for (uint k = 0; k < me.NumShaders; k++)
            {
                uint si = a.ShaderIndices[me.ShaderIndicesOffset + k];
                var se = a.ShaderEntries[si];
                var raw = lib.ShaderCode[si]; var code = raw;
                if (se.Size < se.UncompressedSize)
                {
                    code = new byte[se.UncompressedSize];
                    CUE4Parse.Compression.Compression.Decompress(raw, 0, raw.Length, code, 0, code.Length, CUE4Parse.Compression.CompressionMethod.LZ4);
                }
                File.WriteAllBytes(Path.Combine(args[2], $"{k:D3}_{se.Frequency}.bin"), code);
                log.AppendLine($"  {k:D3} freq {se.Frequency} lib {si} {raw.Length} -> {code.Length}");
            }
        }
        File.WriteAllText(Path.Combine(args[2], "shadermap.txt"), log.ToString());
        Console.WriteLine(log.ToString());
        break;
    }
    case "json":
        var jp = Norm(args[1]);   // (a level: its .umap as given)
        var pkg = provider.LoadPackage(jp.EndsWith(".umap") ? jp : jp.Replace(".uasset", "") + ".uasset");
        var all = pkg.GetExports().ToList();
        File.WriteAllText(args[2], Newtonsoft.Json.JsonConvert.SerializeObject(all, Newtonsoft.Json.Formatting.Indented));
        Console.WriteLine($"{all.Count} exports -> {args[2]}");
        break;
    case "anim":
    {
        // anim <list> <outdir>: animation sequences (a pak path a line) sampled per frame, every bone of the skeleton:
        // <outdir>/<name>.json = { name, fps, frames, additive, ref: {bone: [tx,ty,tz, qx,qy,qz,qw, sx,sy,sz]},
        // bones: {bone: [[tx,ty,tz, qx,qy,qz,qw, sx,sy,sz] per frame]} } in Unreal's frame (cm, bone-local)
        Directory.CreateDirectory(args[2]);
        int na = 0;
        foreach (var raw in File.ReadAllLines(args[1]).Select(l => l.Trim()).Where(l => l.Length > 0))
        {
            try
            {
                var seq = provider.LoadPackageObject<CUE4Parse.UE4.Assets.Exports.Animation.UAnimSequence>(Norm(raw).Replace(".uasset", ""));
                var set = CUE4Parse_Conversion.Animations.AnimConverter.ConvertAnims(seq);
                var cs = set.Sequences[0];
                var refSk = set.Skeleton.ReferenceSkeleton;
                float[] T(FTransform t) => new[] { (float)t.Translation.X, (float)t.Translation.Y, (float)t.Translation.Z,
                    (float)t.Rotation.X, (float)t.Rotation.Y, (float)t.Rotation.Z, (float)t.Rotation.W, (float)t.Scale3D.X, (float)t.Scale3D.Y, (float)t.Scale3D.Z };
                var refPose = new Dictionary<string, float[]>(); var bones = new Dictionary<string, List<float[]>>();
                for (int b = 0; b < refSk.FinalRefBoneInfo.Length; b++)
                {
                    string bn = refSk.FinalRefBoneInfo[b].Name.Text;
                    var rp = refSk.FinalRefBonePose[b];
                    refPose[bn] = T(rp);
                    var frames = new List<float[]>();
                    var track = b < cs.Tracks.Count ? cs.Tracks[b] : null;
                    for (int fr = 0; fr < Math.Max(cs.NumFrames, 1); fr++)
                    {
                        var q = rp.Rotation; var p = rp.Translation; var sc = rp.Scale3D;
                        track?.GetBoneTransform(fr, cs.NumFrames, ref q, ref p, ref sc);
                        frames.Add(T(new FTransform(q, p, sc)));
                    }
                    bones[bn] = frames;
                }
                var outp = new { name = seq.Name, fps = cs.FramesPerSecond, frames = cs.NumFrames, additive = cs.IsAdditive, @ref = refPose, bones };
                File.WriteAllText(Path.Combine(args[2], seq.Name + ".json"), Newtonsoft.Json.JsonConvert.SerializeObject(outp));
                na++;
            }
            catch (Exception e) { Console.WriteLine($"FAILED {raw}: {e.Message}"); }
        }
        Console.WriteLine($"{na} animations -> {args[2]}");
        break;
    }
    case "jsonall":
        // jsonall <regex> <outdir>: every matching .uasset's or .umap's exports as <outdir>/<name>.json
        var rxa = new System.Text.RegularExpressions.Regex(args[1], System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        Directory.CreateDirectory(args[2]);
        int nj = 0;
        foreach (var f in provider.Files.Keys.Where(k => (k.EndsWith(".uasset") || k.EndsWith(".umap")) && rxa.IsMatch(k)).ToList())
        {
            try
            {
                var ex = provider.LoadPackage(f).GetExports().ToList();
                File.WriteAllText(Path.Combine(args[2], Path.GetFileNameWithoutExtension(f) + ".json"), Newtonsoft.Json.JsonConvert.SerializeObject(ex, Newtonsoft.Json.Formatting.Indented));
                nj++;
            }
            catch (Exception e) { Console.WriteLine($"FAILED {f}: {e.Message}"); }
        }
        Console.WriteLine($"{nj} packages -> {args[2]}");
        break;
    case "raw":
        // raw <regex> <outdir>: every file whose pak path matches, written as it is (its own name)
        Directory.CreateDirectory(args[2]);
        var rrx = new System.Text.RegularExpressions.Regex(args[1], System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        int nr = 0;
        foreach (var (key, file) in provider.Files)
            if (rrx.IsMatch(key)) { File.WriteAllBytes(Path.Combine(args[2], key.Split('/').Last()), file.Read()); nr++; }
        Console.WriteLine($"{nr} files -> {args[2]}");
        break;
    case "export":
        CUE4Parse_Conversion.Textures.TextureDecoder.UseAssetRipperTextureDecoder = true;
        var session = new CUE4Parse_Conversion.ExportSession { MaxDegreeOfParallelism = 2 };
        int queued = 0;
        foreach (var raw in File.ReadAllLines(args[1]))
        {
            var line = Norm(raw.Trim());
            if (line.Length == 0 || line.StartsWith("#")) continue;
            if (!line.Contains('.')) line += "." + line.Split('/').Last();
            try { session.Add(provider.LoadPackageObject(line)); queued++; }
            catch (Exception e) { Console.WriteLine($"MISSING {line}: {e.Message}"); }
        }
        // (args[3]: "all" writes every LOD, <name>_LOD1.glb ...: the stations' merged meshes pick theirs by a triangle budget)
        var quality = args.Length > 3 && args[3] == "all" ? CUE4Parse_Conversion.Options.EMeshQuality.All
                    : args.Length > 3 && args[3] == "lowest" ? CUE4Parse_Conversion.Options.EMeshQuality.Lowest : CUE4Parse_Conversion.Options.EMeshQuality.Highest;
        var opts = new CUE4Parse_Conversion.Options.ExportOptions(meshFormat: CUE4Parse_Conversion.Options.EMeshFormat.Gltf2,
            meshQuality: quality, textureFormat: CUE4Parse_Conversion.Options.ETextureFormat.Png,
            materialDepth: EMaterialDepth.TopLayerOnly);
        var results = session.RunAsync(args[2], opts).GetAwaiter().GetResult();
        foreach (var r in results) if (!r.Success) Console.WriteLine($"FAILED {r.ObjectPath}: {r.Error?.Message}");
        Console.WriteLine($"exported {results.Count(r => r.Success)} of {results.Count} (queued {queued})");
        break;
}
