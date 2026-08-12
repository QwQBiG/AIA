#!/usr/bin/env python3
"""
Full-Duplex Engine Diagnostic Tool

Command-line tool for running comprehensive diagnostics on the full-duplex
conversational engine system.
"""

import sys
import os
import argparse

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def main():
    parser = argparse.ArgumentParser(
        description="Run diagnostics for Full-Duplex Conversational Engine"
    )
    parser.add_argument(
        '--save-report', 
        action='store_true',
        help='Save diagnostic report to file'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output filename for diagnostic report'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress console output (only save to file)'
    )
    
    args = parser.parse_args()
    
    try:
        # Import diagnostic tools
        from full_duplex_engine.diagnostic_tools import get_diagnostic_tools
        
        print("Full-Duplex Engine Diagnostic Tool")
        print("=" * 50)
        
        # Run diagnostics
        diagnostic_tools = get_diagnostic_tools()
        print("Running comprehensive system diagnostics...")
        print("This may take a few moments...\n")
        
        diagnostics = diagnostic_tools.run_full_diagnostics()
        
        # Generate and display report
        if not args.quiet:
            report = diagnostic_tools.generate_user_friendly_report(diagnostics)
            print(report)
        
        # Save report if requested
        if args.save_report or args.output:
            filename = diagnostic_tools.save_diagnostic_report(diagnostics, args.output)
            if filename:
                print(f"\nDiagnostic report saved to: {filename}")
            else:
                print("\nFailed to save diagnostic report")
                return 1
        
        # Return appropriate exit code
        if diagnostics.overall_status == "fail":
            print("\nDiagnostics completed with FAILURES")
            return 1
        elif diagnostics.overall_status == "warning":
            print("\nDiagnostics completed with WARNINGS")
            return 0
        else:
            print("\nDiagnostics completed successfully")
            return 0
            
    except ImportError as e:
        print(f"Error: Cannot import diagnostic tools: {e}")
        print("Make sure you're running from the correct directory and dependencies are installed")
        return 1
    except Exception as e:
        print(f"Error running diagnostics: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())