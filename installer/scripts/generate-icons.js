/**
 * Generate placeholder ICO files for the Windows installer
 * 
 * This script creates valid ICO files with a simple colored square design.
 * These are placeholder icons that should be replaced with proper branded icons
 * before production release.
 */

const fs = require('fs');
const path = require('path');

const icons = [
  { filename: 'icon.ico', color: { r: 66, g: 133, b: 244 }, description: 'Main application icon (blue)' },
  { filename: 'installer.ico', color: { r: 52, g: 168, b: 83 }, description: 'Installer icon (green)' },
  { filename: 'uninstaller.ico', color: { r: 234, g: 67, b: 53 }, description: 'Uninstaller icon (red)' },
  { filename: 'tray.ico', color: { r: 251, g: 188, b: 5 }, description: 'System tray icon (yellow)' },
];

/**
 * Create a BMP image data for a solid color square
 */
function createBmpData(size, color) {
  const headerSize = 40;
  const rowSize = Math.ceil((size * 32) / 32) * 4;
  const pixelDataSize = rowSize * size;
  const andMaskRowSize = Math.ceil(size / 32) * 4;
  const andMaskSize = andMaskRowSize * size;
  
  const totalSize = headerSize + pixelDataSize + andMaskSize;
  const buffer = Buffer.alloc(totalSize);
  let offset = 0;

  // BITMAPINFOHEADER
  buffer.writeUInt32LE(40, offset); offset += 4;
  buffer.writeInt32LE(size, offset); offset += 4;
  buffer.writeInt32LE(size * 2, offset); offset += 4;
  buffer.writeUInt16LE(1, offset); offset += 2;
  buffer.writeUInt16LE(32, offset); offset += 2;
  buffer.writeUInt32LE(0, offset); offset += 4;
  buffer.writeUInt32LE(pixelDataSize + andMaskSize, offset); offset += 4;
  buffer.writeInt32LE(0, offset); offset += 4;
  buffer.writeInt32LE(0, offset); offset += 4;
  buffer.writeUInt32LE(0, offset); offset += 4;
  buffer.writeUInt32LE(0, offset); offset += 4;

  // Pixel data (BGRA format, bottom-up)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const centerX = size / 2;
      const centerY = size / 2;
      const dx = Math.abs(x - centerX);
      const dy = Math.abs(y - centerY);
      const cornerRadius = size * 0.15;
      
      let alpha = 255;
      if (dx > centerX - cornerRadius && dy > centerY - cornerRadius) {
        const cornerDist = Math.sqrt(
          Math.pow(dx - (centerX - cornerRadius), 2) + 
          Math.pow(dy - (centerY - cornerRadius), 2)
        );
        if (cornerDist > cornerRadius) {
          alpha = 0;
        }
      }

      buffer.writeUInt8(color.b, offset++);
      buffer.writeUInt8(color.g, offset++);
      buffer.writeUInt8(color.r, offset++);
      buffer.writeUInt8(alpha, offset++);
    }
  }

  // AND mask
  for (let i = 0; i < andMaskSize; i++) {
    buffer.writeUInt8(0, offset++);
  }

  return buffer;
}

/**
 * Create an ICO file with multiple sizes
 */
function createIcoFile(color) {
  const sizes = [16, 32, 48, 256];
  const images = [];
  
  for (const size of sizes) {
    images.push(createBmpData(size, color));
  }

  const headerSize = 6;
  const dirEntrySize = 16;
  const dirSize = headerSize + (dirEntrySize * sizes.length);
  let totalSize = dirSize;
  for (const img of images) {
    totalSize += img.length;
  }

  const buffer = Buffer.alloc(totalSize);
  let offset = 0;

  // ICONDIR header
  buffer.writeUInt16LE(0, offset); offset += 2;
  buffer.writeUInt16LE(1, offset); offset += 2;
  buffer.writeUInt16LE(sizes.length, offset); offset += 2;

  // ICONDIRENTRY for each image
  let imageOffset = dirSize;
  for (let i = 0; i < sizes.length; i++) {
    const size = sizes[i];
    const imageData = images[i];
    
    buffer.writeUInt8(size === 256 ? 0 : size, offset++);
    buffer.writeUInt8(size === 256 ? 0 : size, offset++);
    buffer.writeUInt8(0, offset++);
    buffer.writeUInt8(0, offset++);
    buffer.writeUInt16LE(1, offset); offset += 2;
    buffer.writeUInt16LE(32, offset); offset += 2;
    buffer.writeUInt32LE(imageData.length, offset); offset += 4;
    buffer.writeUInt32LE(imageOffset, offset); offset += 4;
    
    imageOffset += imageData.length;
  }

  // Write image data
  for (const imageData of images) {
    imageData.copy(buffer, offset);
    offset += imageData.length;
  }

  return buffer;
}

/**
 * Main function to generate all icon files
 */
function generateIcons() {
  const assetsDir = path.join(__dirname, '../assets');
  
  if (!fs.existsSync(assetsDir)) {
    fs.mkdirSync(assetsDir, { recursive: true });
  }

  console.log('Generating placeholder icons for Windows installer...\n');

  for (const icon of icons) {
    const iconPath = path.join(assetsDir, icon.filename);
    const iconData = createIcoFile(icon.color);
    
    fs.writeFileSync(iconPath, iconData);
    console.log(`Created ${icon.filename} - ${icon.description}`);
  }

  console.log('\nAll icons generated successfully!');
  console.log('\nNote: These are placeholder icons. Replace them with properly');
  console.log('designed branded icons before production release.');
}

generateIcons();
