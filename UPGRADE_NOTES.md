# Upgrade Notes - Locking Mechanism Fixes

## For Users

### What Changed?

This update fixes critical bugs that caused "silent failures" when changing wallbox settings like max current, charging mode, etc.

**Before:**
- Settings sometimes didn't apply with no error message
- You had to manually retry changes
- Integration occasionally became unresponsive requiring Home Assistant restart

**After:**
- Settings reliably apply within 5-15 seconds
- Failed updates automatically retry
- Integration provides clear feedback in logs
- No more unresponsive states requiring restart

### Do I Need to Do Anything?

**No manual action required!** The integration will automatically use the new code after:
1. Updating the integration (via HACS or manually)
2. Restarting Home Assistant

### How to Verify It's Working

**Enable debug logging** (optional but recommended):

Add to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.alfen_wallbox: debug
```

Then restart Home Assistant.

**Test it:**
1. Change a setting (e.g., max current)
2. Check the logs - you should see:
   - `Queued value update for 2129_0 to 16` (immediate)
   - `Set 2129_0 value 16` (within ~5 seconds)

**If something fails:**
- You'll see: `Failed to update 2129_0 to 16 - will retry on next update cycle`
- The update will automatically retry every 5 seconds until it succeeds

### Common Questions

**Q: Will my existing settings be affected?**
A: No, all your configured settings remain unchanged.

**Q: Why do changes take 5 seconds now?**
A: Changes were always queued and sent on the next update cycle (5 second default). The difference is they now reliably apply instead of silently failing.

**Q: What if I see "Failed to update" warnings?**
A: This is normal if there are temporary network issues or if the wallbox is busy. The update will retry automatically. If you see persistent failures (5+ retries), check:
- Network connectivity to the wallbox
- Wallbox is powered on and responsive
- No one else is logged into the wallbox (app conflict)

**Q: Do I need to reconfigure anything?**
A: No, the integration will work exactly as before, just more reliably.

---

## For Developers

### Breaking Changes

#### 1. `set_value()` is now async

**Old code:**
```python
device.set_value("2129_0", 16)
```

**New code:**
```python
await device.set_value("2129_0", 16)
```

All built-in entity platforms have been updated. If you have custom code calling `set_value()`, you must add `await`.

#### 2. Boolean locks replaced with asyncio.Lock

**Old code:**
```python
if self.lock:
    return None
self.lock = True
try:
    # work
finally:
    self.lock = False
```

**New code:**
```python
async with self._lock:
    # work
```

If you have custom code that accesses `device.lock` or `device.updating`, update it to use the new lock objects or remove it entirely.

### New Lock Objects

Three separate locks for different purposes:

```python
self._lock                 # Serializes HTTP requests
self._updating_lock        # Serializes update cycles
self._update_values_lock   # Protects update_values dict
```

### Response Handling Changes

Methods `_post()`, `_get()`, and `_update_value()` now return processed data instead of response objects:

**Old:**
```python
response = await self._post(cmd, payload)
if response:
    data = await response.json()  # BUG: response might be closed
```

**New:**
```python
data = await self._post(cmd, payload)  # Returns dict, not response
if data:
    # use data directly
```

### Testing Your Code

If you have custom modifications:

1. **Search for `device.lock` or `device.updating`** - These no longer exist
2. **Search for `device.set_value(`** - Add `await` if missing
3. **Check response handling** - Update if you process responses from `_post()`, `_get()`, `_update_value()`
4. **Test concurrent operations** - The new locks handle this better
5. **Test error recovery** - Locks now release properly on errors

### Running Tests

```bash
# Syntax check
python3 -m py_compile custom_components/alfen_wallbox/*.py

# Install in Home Assistant
cp -r custom_components/alfen_wallbox ~/.homeassistant/custom_components/

# Restart Home Assistant
ha core restart

# Enable debug logging and monitor
tail -f ~/.homeassistant/home-assistant.log | grep alfen_wallbox
```

### Understanding the New Flow

**Setting a value:**
```
1. Entity calls: await device.set_value("2129_0", 16)
2. Value queued in update_values dict (with lock protection)
3. Debug log: "Queued value update for 2129_0 to 16"
4. On next coordinator cycle (~5 sec):
   5. Coordinator calls device.async_update()
   6. async_update() processes update_values
   7. Calls _update_value() for each queued value
   8. If success: removes from queue, updates properties
   9. If failure: keeps in queue, logs warning, retries later
```

**Request handling:**
```
1. Request arrives (POST/GET)
2. Acquire _lock (waits if held)
3. Send HTTP request in async with context manager
4. Process response INSIDE context manager
5. Return processed data (dict/str)
6. Lock auto-released by context manager
```

### Common Pitfalls

❌ **DON'T:**
```python
device.set_value("2129_0", 16)  # Missing await
if device.lock: ...              # lock no longer exists
self.lock = False                # Manual lock management
```

✅ **DO:**
```python
await device.set_value("2129_0", 16)
async with device._lock: ...     # Use context manager
# Lock auto-released, don't touch it manually
```

---

## Rollback Instructions

If you experience issues and need to rollback:

1. **Via git:**
   ```bash
   cd custom_components/alfen_wallbox
   git checkout <previous-commit-hash>
   ```

2. **Via HACS:**
   - Go to HACS → Integrations
   - Find Alfen Wallbox
   - Click → Redownload → Select previous version

3. **Restart Home Assistant**

**Please report issues** at: https://github.com/leeyuentuen/alfen_wallbox/issues

Include:
- Home Assistant version
- Integration version
- Relevant logs (with debug enabled)
- Steps to reproduce

---

## Support

- **Documentation:** [LOCKING_FIXES.md](LOCKING_FIXES.md) - Technical details
- **Issues:** https://github.com/leeyuentuen/alfen_wallbox/issues
- **Discussions:** GitHub Discussions tab
- **Home Assistant Community:** Search for "Alfen Wallbox"

---

## Credits

These fixes address issues reported by the community. Thank you to all users who reported silent failures and provided debugging information.
