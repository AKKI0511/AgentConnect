#!/usr/bin/env python3
"""
Test runner for capability discovery tests.

This script runs the capability discovery tests with pretty formatting
and visual output to show the test results clearly.
"""

import sys
import os
import asyncio
import subprocess
import argparse

# ANSI colors for pretty output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner(text):
    """Print a pretty banner with the given text."""
    width = 80
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*width}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(width)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*width}{Colors.ENDC}\n")

def print_section(text):
    """Print a section header."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.BLUE}{'-' * len(text)}{Colors.ENDC}\n")

def run_tests(args):
    """Run the capability discovery tests."""
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the test files
    impl_test_file = os.path.join(script_dir, "core", "registry", "test_capability_discovery_impl.py")
    e2e_test_file = os.path.join(script_dir, "core", "registry", "test_capability_discovery_e2e.py")
    integration_test_file = os.path.join(script_dir, "core", "registry", "test_integration.py")
    
    # Check if the test files exist
    if not os.path.exists(impl_test_file):
        print(f"{Colors.RED}Error: Implementation test file not found at {impl_test_file}{Colors.ENDC}")
        return 1
    
    if not os.path.exists(e2e_test_file):
        print(f"{Colors.RED}Error: End-to-end test file not found at {e2e_test_file}{Colors.ENDC}")
        return 1
    
    if not os.path.exists(integration_test_file):
        print(f"{Colors.RED}Error: Integration test file not found at {integration_test_file}{Colors.ENDC}")
        return 1
    
    print_banner("AgentConnect Capability Discovery Tests")
    
    # Run the tests
    result = 0
    
    if args.impl or args.all:
        print_section("Running Implementation Unit Tests")
        impl_result = subprocess.run(
            [sys.executable, "-m", "pytest", impl_test_file, "-v", "--color=yes"],
            capture_output=args.quiet
        )
        if impl_result.returncode != 0:
            result = impl_result.returncode
            if args.quiet:
                print(f"{Colors.RED}Implementation tests failed!{Colors.ENDC}")
                print(impl_result.stdout.decode('utf-8'))
                print(impl_result.stderr.decode('utf-8'))
        elif args.quiet:
            print(f"{Colors.GREEN}Implementation tests passed!{Colors.ENDC}")
    
    if args.e2e or args.all:
        print_section("Running End-to-End Tests")
        e2e_result = subprocess.run(
            [sys.executable, "-m", "pytest", e2e_test_file, "-v", "--color=yes"],
            capture_output=args.quiet
        )
        if e2e_result.returncode != 0:
            result = e2e_result.returncode
            if args.quiet:
                print(f"{Colors.RED}End-to-end tests failed!{Colors.ENDC}")
                print(e2e_result.stdout.decode('utf-8'))
                print(e2e_result.stderr.decode('utf-8'))
        elif args.quiet:
            print(f"{Colors.GREEN}End-to-end tests passed!{Colors.ENDC}")

    if args.integration or args.all:
        print_section("Running Integration Tests")
        integration_result = subprocess.run(
            [sys.executable, "-m", "pytest", integration_test_file, "-v", "--color=yes"],
            capture_output=args.quiet
        )
        if integration_result.returncode != 0:
            result = integration_result.returncode
            if args.quiet:
                print(f"{Colors.RED}Integration tests failed!{Colors.ENDC}")
                print(integration_result.stdout.decode('utf-8'))
                print(integration_result.stderr.decode('utf-8'))
        elif args.quiet:
            print(f"{Colors.GREEN}Integration tests passed!{Colors.ENDC}")
    
    if result == 0:
        print_banner("All Tests Passed!")
    else:
        print_banner("Some Tests Failed!")
    
    return result

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run capability discovery tests")
    parser.add_argument("--impl", action="store_true", help="Run implementation tests only")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--quiet", action="store_true", help="Suppress test output except for errors")
    
    args = parser.parse_args()
    
    # If no specific tests are requested, run all tests
    if not (args.impl or args.e2e or args.integration or args.all):
        args.all = True
    
    return run_tests(args)

if __name__ == "__main__":
    sys.exit(main()) 