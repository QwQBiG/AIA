#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v4.4 Module Functionality Test"""

import sys
import time

print('='*60)
print('v4.4 Module Functionality Test')
print('='*60)

# Test 1: Super Startup Optimizer
print('\n[Test 1] Super Startup Optimizer')
try:
    from src.super_startup_optimizer import get_startup_optimizer
    optimizer = get_startup_optimizer()
    
    start = time.time()
    asyncio_mod = optimizer.lazy_import('asyncio')
    first_time = (time.time() - start) * 1000
    
    start = time.time()
    asyncio_mod2 = optimizer.lazy_import('asyncio')
    second_time = (time.time() - start) * 1000
    
    print(f'  OK - Import asyncio: first {first_time:.1f}ms, second {second_time:.1f}ms')
    print(f'  OK - Cache speedup: {first_time/second_time:.1f}x')
    
    with optimizer.measure_time('test_operation'):
        time.sleep(0.01)
    
    print(f'  OK - Time measurement: {optimizer._startup_timings.get("test_operation", 0):.1f}ms')
    print('  OK - Super Startup Optimizer test passed!')
except Exception as e:
    print(f'  FAIL - Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Smart Preload Manager
print('\n[Test 2] Smart Preload Manager')
try:
    from src.smart_preload_manager import get_preload_manager
    manager = get_preload_manager()
    
    manager.record_import('json', 25.0, success=True)
    manager.record_import('json', 28.0, success=True)
    
    stats = manager.get_usage_stats('json')
    print(f'  OK - Module import count: {stats.import_count}')
    print(f'  OK - Avg load time: {stats.avg_load_time:.1f}ms')
    print(f'  OK - Usage frequency: {stats.usage_frequency:.2f}/h')
    print('  OK - Smart Preload Manager test passed!')
except Exception as e:
    print(f'  FAIL - Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: LLM Connection Pool
print('\n[Test 3] LLM Connection Pool Manager')
try:
    from src.llm_connection_pool import get_llm_pool, ConnectionConfig
    
    config = ConnectionConfig(base_url='http://localhost:11434', model='test', pool_size=2)
    pool = get_llm_pool(config)
    
    stats = pool.get_stats()
    print(f'  OK - Pool stats: total={stats.total_connections}, active={stats.active_connections}')
    print(f'  OK - Pool utilization: {stats.pool_utilization*100:.1f}%')
    print('  OK - LLM Connection Pool test passed!')
except Exception as e:
    print(f'  FAIL - Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Adaptive Performance Tuner
print('\n[Test 4] Adaptive Performance Tuner')
try:
    from src.adaptive_performance_tuner import get_performance_tuner
    tuner = get_performance_tuner()
    
    tuner.record_metric('test_latency', 100.0)
    tuner.record_metric('test_latency', 110.0)
    tuner.record_metric('test_latency', 95.0)
    
    stats = tuner.get_metric_stats('test_latency')
    print(f'  OK - Metric stats: mean={stats.mean:.1f}ms, min={stats.min:.1f}ms, max={stats.max:.1f}ms')
    print(f'  OK - P95: {stats.p95:.1f}ms, P99: {stats.p99:.1f}ms')
    print(f'  OK - Trend: {stats.trend} ({stats.trend_rate:.1%})')
    print('  OK - Adaptive Performance Tuner test passed!')
except Exception as e:
    print(f'  FAIL - Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Full Chain Monitor
print('\n[Test 5] Full Chain Monitor')
try:
    from src.full_chain_monitor import get_full_chain_monitor
    monitor = get_full_chain_monitor()
    
    with monitor.trace('test_operation'):
        time.sleep(0.01)
    
    stats = monitor.get_stats()
    print(f'  OK - Trace stats: total={stats.total_traces}, success={stats.success_traces}')
    print(f'  OK - Avg duration: {stats.avg_duration:.1f}ms')
    print(f'  OK - P95 duration: {stats.p95_duration:.1f}ms')
    print('  OK - Full Chain Monitor test passed!')
except Exception as e:
    print(f'  FAIL - Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n' + '='*60)
print('SUCCESS: All v4.4 modules tested successfully!')
print('READY TO USE!')
print('='*60)
