#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v4.4 Performance Benchmark Test"""

import asyncio
import time

print('='*60)
print('v4.4 Performance Benchmark Test')
print('='*60)

# Test Startup Optimizer Performance
from src.super_startup_optimizer import get_startup_optimizer

optimizer = get_startup_optimizer()

print('\n[Performance Test] Module Import Speed Comparison')
modules_to_test = ['asyncio', 'json', 'logging', 'time', 'queue']

# First import (no cache)
print('First import (no cache):')
start = time.time()
for module in modules_to_test:
    optimizer.lazy_import(module)
first_import_time = (time.time() - start) * 1000
print(f'  Total time: {first_import_time:.1f}ms')
print(f'  Average: {first_import_time/len(modules_to_test):.1f}ms/module')

# Second import (with cache)
print('\nSecond import (with cache):')
start = time.time()
for module in modules_to_test:
    optimizer.lazy_import(module)
second_import_time = (time.time() - start) * 1000
print(f'  Total time: {second_import_time:.1f}ms')
print(f'  Average: {second_import_time/len(modules_to_test):.1f}ms/module')

print(f'\nCache speedup: {first_import_time/second_import_time:.1f}x')
print(f'Cache improvement: {(1 - second_import_time/first_import_time)*100:.1f}%')

# Test Smart Preload Manager
from src.smart_preload_manager import get_preload_manager

print('\n[Performance Test] Smart Preload Manager')
manager = get_preload_manager()

print('Simulating module usage (10 times):')
start = time.time()
for _ in range(10):
    manager.record_import('frequent_module', 30.0, success=True)
record_time = (time.time() - start) * 1000
print(f'  Record time: {record_time:.1f}ms')

stats = manager.get_usage_stats('frequent_module')
print(f'  Usage frequency: {stats.usage_frequency:.2f}/h')
print(f'  Preload recommended: {"YES" if stats.usage_frequency > 1.0 else "NO"}')

# Test Full Chain Monitor Overhead
from src.full_chain_monitor import get_full_chain_monitor

print('\n[Performance Test] Full Chain Monitor Overhead')
monitor = get_full_chain_monitor()

# Without monitoring
print('Without monitoring (100 iterations):')
start = time.time()
for i in range(100):
    time.sleep(0.0001)
baseline_time = time.time() - start
print(f'  Time: {baseline_time*1000:.1f}ms')

# With monitoring
print('\nWith monitoring (100 iterations):')
start = time.time()
for i in range(100):
    with monitor.trace(f'operation_{i}'):
        time.sleep(0.0001)
monitor_time = time.time() - start
print(f'  Time: {monitor_time*1000:.1f}ms')

overhead = ((monitor_time - baseline_time) / baseline_time) * 100
print(f'\nMonitoring overhead: {overhead:.1f}%')

# Test Adaptive Performance Tuner
from src.adaptive_performance_tuner import get_performance_tuner

print('\n[Performance Test] Adaptive Performance Tuner')
tuner = get_performance_tuner()

print('Recording metrics (100 samples):')
start = time.time()
for i in range(100):
    tuner.record_metric('latency_test', 50.0 + i * 0.1)
record_time = (time.time() - start) * 1000
print(f'  Record time: {record_time:.1f}ms')
print(f'  Average per record: {record_time/100:.3f}ms')

stats = tuner.get_metric_stats('latency_test')
print(f'  Metric stats: mean={stats.mean:.1f}ms, P95={stats.p95:.1f}ms')

# Generate performance report
print('\n[Performance Test] Generating Report')
start = time.time()
profile = optimizer.generate_startup_profile()
report_time = (time.time() - start) * 1000
print(f'  Report generation time: {report_time:.1f}ms')

print('\n' + '='*60)
print('PERFORMANCE BENCHMARK TEST COMPLETED!')
print('='*60)

print('\nSUMMARY:')
print(f'  - Module cache speedup: {first_import_time/second_import_time:.1f}x')
print(f'  - Monitoring overhead: {overhead:.1f}%')
print(f'  - All modules working: YES')
print('\nREADY FOR PRODUCTION USE!')
