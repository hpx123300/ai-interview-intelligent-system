// 使用 macOS Vision 框架对图片做 OCR（中文 + 英文），用于识别 JD 截图。
// 用法：swift ocr_vision.swift <image_path>
// 输出：每行一段识别文本。

import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else {
    FileHandle.standardError.write("用法：swift ocr_vision.swift <image_path>\n".data(using: .utf8)!)
    exit(2)
}

let path = CommandLine.arguments[1]
guard let image = NSImage(contentsOfFile: path),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("无法读取图片：\(path)\n".data(using: .utf8)!)
    exit(3)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
do {
    try handler.perform([request])
} catch {
    FileHandle.standardError.write("OCR 失败：\(error)\n".data(using: .utf8)!)
    exit(4)
}

var out = ""
for observation in request.results ?? [] {
    if let top = observation.topCandidates(1).first {
        out += top.string + "\n"
    }
}
print(out, terminator: "")
