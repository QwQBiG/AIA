/**
 * Build script for AI VTuber Digital Human Windows Installer
 * 
 * Usage:
 *   npm run build:installer
 *   npm run build:installer -- --version=1.2.3
 * 
 * Requirements: 6.1, 6.3, 6.4, 6.5
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { execSync, spawn } from 'child_process';

interface BuildOptions {
  version?: string;
  outputDir?: string;
}

interface BuildResult {
  success: boolean;
  installerPath?: string;
  checksumPath?: string;
  fileSize?: number;
  checksum?: string;
  error?: string;
}

/**
 * Parse command line arguments
 */
function parseArgs(): BuildOptions {
  const args = process.argv.slice(2);
  const options: BuildOptions = {};

  for (const arg of args) {
    if (arg.startsWith('--version=')) {
      options.version = arg.split('=')[1];
    } else if (arg.startsWith('--output=')) {
      options.outputDir = arg.split('=')[1];
    }
  }

  return options;
}

/**
 * Get version from package.json or command line
 */
function getVersion(options: BuildOptions): string {
  if (options.version) {
    return options.version;
  }

  const packageJsonPath = path.join(__dirname, '..', 'package.json');
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
  return packageJson.version || '1.0.0';
}

/**
 * Update version in package.json if specified via command line
 */
function updatePackageVersion(version: string): void {
  const packageJsonPath = path.join(__dirname, '..', 'package.json');
  const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
  
  if (packageJson.version !== version) {
    packageJson.version = version;
    fs.writeFileSync(packageJsonPath, JSON.stringify(packageJson, null, 2) + '\n');
    console.log(`Updated package.json version to ${version}`);
  }
}

/**
 * Calculate SHA256 checksum of a file
 * Property 4: Checksum Determinism - same content always produces same hash
 */
export function calculateChecksum(filePath: string): string {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

/**
 * Generate checksum file for the installer
 */
function generateChecksumFile(installerPath: string, outputDir: string): string {
  const checksum = calculateChecksum(installerPath);
  const fileName = path.basename(installerPath);
  const checksumFileName = `${fileName}.sha256`;
  const checksumPath = path.join(outputDir, checksumFileName);
  
  const checksumContent = `${checksum}  ${fileName}\n`;
  fs.writeFileSync(checksumPath, checksumContent);
  
  return checksumPath;
}

/**
 * Get file size in human readable format
 */
function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  
  return `${size.toFixed(2)} ${units[unitIndex]}`;
}

/**
 * Find the generated installer file
 */
function findInstallerFile(outputDir: string, version: string): string | null {
  if (!fs.existsSync(outputDir)) {
    return null;
  }

  const files = fs.readdirSync(outputDir);
  const installerFile = files.find(f => 
    f.endsWith('.exe') && 
    f.includes('Setup') &&
    !f.endsWith('.blockmap')
  );

  return installerFile ? path.join(outputDir, installerFile) : null;
}

/**
 * Compile TypeScript files
 */
function compileTypeScript(): void {
  console.log('Compiling TypeScript...');
  execSync('npm run build', { 
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit' 
  });
}

/**
 * Run electron-builder
 */
async function runElectronBuilder(): Promise<void> {
  console.log('Running electron-builder...');
  
  return new Promise((resolve, reject) => {
    const builder = spawn('npx', ['electron-builder', '--win'], {
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit',
      shell: true
    });

    builder.on('close', (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`electron-builder exited with code ${code}`));
      }
    });

    builder.on('error', (err) => {
      reject(err);
    });
  });
}

/**
 * Main build function
 */
export async function build(options: BuildOptions = {}): Promise<BuildResult> {
  const startTime = Date.now();
  
  try {
    console.log('='.repeat(60));
    console.log('AI VTuber Digital Human - Windows Installer Build');
    console.log('='.repeat(60));

    // Get and update version
    const version = getVersion(options);
    console.log(`\nVersion: ${version}`);
    updatePackageVersion(version);

    // Determine output directory
    const outputDir = options.outputDir || path.join(__dirname, '..', 'dist', 'installer');
    console.log(`Output directory: ${outputDir}`);

    // Compile TypeScript
    compileTypeScript();

    // Run electron-builder
    await runElectronBuilder();

    // Find the generated installer
    const installerPath = findInstallerFile(outputDir, version);
    if (!installerPath) {
      throw new Error('Installer file not found after build');
    }

    // Get file size
    const stats = fs.statSync(installerPath);
    const fileSize = stats.size;

    // Generate checksum
    const checksumPath = generateChecksumFile(installerPath, outputDir);
    const checksum = calculateChecksum(installerPath);

    // Calculate build time
    const buildTime = ((Date.now() - startTime) / 1000).toFixed(2);

    // Output build information
    console.log('\n' + '='.repeat(60));
    console.log('Build Complete!');
    console.log('='.repeat(60));
    console.log(`\nInstaller: ${installerPath}`);
    console.log(`Size: ${formatFileSize(fileSize)} (${fileSize} bytes)`);
    console.log(`SHA256: ${checksum}`);
    console.log(`Checksum file: ${checksumPath}`);
    console.log(`Build time: ${buildTime}s`);
    console.log('');

    return {
      success: true,
      installerPath,
      checksumPath,
      fileSize,
      checksum
    };

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('\nBuild failed:', errorMessage);
    
    return {
      success: false,
      error: errorMessage
    };
  }
}

// Run if executed directly
if (require.main === module) {
  const options = parseArgs();
  build(options).then(result => {
    process.exit(result.success ? 0 : 1);
  });
}
