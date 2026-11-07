import path from "node:path";
import {fileURLToPath,pathToFileURL} from "node:url";
import fs from "node:fs/promises";
const workspaceDir=path.dirname(fileURLToPath(import.meta.url));
const skill="/Users/yhx/.codex/plugins/cache/openai-primary-runtime/presentations/26.1104.11149/skills/presentations";
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,"container_tools/artifact_tool_utils.mjs")).href);
const result=await finalizePresentation({
 workspaceDir,
 candidatePath:path.join(workspaceDir,"build/candidate.pptx"),
 finalPath:path.join(workspaceDir,"output/Cache映射与替换策略_小组实验.pptx"),
 pythonExecutable:"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
 integrityValidatorPath:path.join(skill,"container_tools/inspect_presentation_package_integrity.py"),
 layoutValidatorPath:path.join(skill,"container_tools/inspect_presentation_layout_geometry.py"),
 explicitTotalSlideCount:16,
 layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-heading-fit","--validate-bullet-geometry",
  ...[2,3,4,5,15].flatMap(n=>["--require-native-table-slide",String(n)])],
 requiredNativeTableOwnerSlides:[2,3,4,5,15],
 requiredNativeChartOwnerSlides:[6,7,8,9,10,11,12,13],
 requiredEmbeddedWorkbookChartOwnerSlides:[6,7,8,9,10,11,12,13],
 fontPolicy:{basis:"design",families:["Arial Unicode MS"]},
 // This host has no load_workspace_dependencies or @oai/artifact-tool runtime.
 // Native structure, font, geometry, arithmetic and workbook checks still run.
 verifyArtifactToolImport:false,
 receiptPath:path.join(workspaceDir,"build/validation.json")
});
await fs.writeFile(path.join(workspaceDir,"build/runtime_note.json"),JSON.stringify({
 artifact_runtime:"Unavailable: package import failed and runtime loader was not exposed",
 renderer:"macOS Quick Look for native charts; OOXML geometry and installed fonts for slide QA",
 native_powerpoint:"Opening the file through the UI was not completed because the connection stalled"
},null,2));
console.log(JSON.stringify(result,null,2));
