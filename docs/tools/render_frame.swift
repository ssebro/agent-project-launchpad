// Rasterize the picker's recorded terminal cells at 2× resolution, without scaling text.
import AppKit
import Foundation

let args = CommandLine.arguments
let cells = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[1]))) as! [[Any]]
let boldMask = Int(args[3])!
let columns = 100, rows = 23
let cellWidth = 10.0, cellHeight = 22.0, padding = 18.0, scale = 2.0
let width = Double(columns) * cellWidth + padding * 2
let height = Double(rows) * cellHeight + padding * 2
func color(_ hex: UInt32) -> NSColor {
    NSColor(srgbRed: Double((hex >> 16) & 255) / 255,
            green: Double((hex >> 8) & 255) / 255,
            blue: Double(hex & 255) / 255, alpha: 1)
}
let background = color(0x101820), foreground = color(0xE5EDF3)
let colors = [1: color(0x67D8EF), 2: color(0xA0AFBC), 3: foreground,
              4: background, 5: color(0x8CD8A0), 6: color(0xE8C47A),
              7: color(0xFF8B8B), 8: color(0xD5A3ED)]
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(width * scale),
    pixelsHigh: Int(height * scale), bitsPerSample: 8, samplesPerPixel: 4,
    hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0,
    bitsPerPixel: 0)!
let context = NSGraphicsContext(bitmapImageRep: bitmap)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
context.cgContext.scaleBy(x: scale, y: scale)
background.setFill()
NSRect(x: 0, y: 0, width: width, height: height).fill()
for cell in cells {
    let row = cell[0] as! Int, column = cell[1] as! Int
    let text = cell[2] as! String, attributes = cell[3] as! Int
    let style = attributes & ~boldMask
    let x = padding + Double(column) * cellWidth
    let y = height - padding - Double(row + 1) * cellHeight
    if style == 3 || style == 4 {
        (style == 3 ? color(0x234C88) : color(0x67D8EF)).setFill()
        NSRect(x: x, y: y, width: cellWidth, height: cellHeight).fill()
    }
    let font = NSFont.monospacedSystemFont(ofSize: 16,
        weight: attributes & boldMask != 0 || style == 1 || style == 4 ? .semibold : .regular)
    (text as NSString).draw(at: NSPoint(x: x, y: y + 2), withAttributes: [
        .font: font, .foregroundColor: colors[style] ?? foreground])
}
NSGraphicsContext.restoreGraphicsState()
try bitmap.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[2]))
