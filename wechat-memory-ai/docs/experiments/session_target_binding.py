"""Read-only identity/liveness proof for an explicitly bound owned target.

Only PID enumeration is used when OpenProcess cannot open the object. An API
error alone never proves death; incomplete enumeration also remains unknown.
"""
import ctypes
K=ctypes.WinDLL('kernel32',use_last_error=True)
K.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];K.OpenProcess.restype=ctypes.c_void_p
K.GetProcessTimes.argtypes=[ctypes.c_void_p,*([ctypes.c_void_p]*4)]
K.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];K.WaitForSingleObject.restype=ctypes.c_ulong
K.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
K.CloseHandle.argtypes=[ctypes.c_void_p]
K.K32EnumProcesses.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong)]

def identity(value):
 if not isinstance(value,dict) or set(value)!={'pid','created'}:raise ValueError('target')
 if type(value['pid']) is not int or not 0<value['pid']<2**32:raise ValueError('pid')
 if type(value['created']) is not int or not 0<value['created']<2**63:raise ValueError('created')
 return value['pid'],value['created']

def probe(pid,expected_created):
 h=K.OpenProcess(0x100000|0x1000,0,pid)
 if not h:
  opening_error=ctypes.get_last_error()
  for capacity in (1024,4096,16384,65536):
   ids=(ctypes.c_ulong*capacity)();used=ctypes.c_ulong()
   if not K.K32EnumProcesses(ids,ctypes.sizeof(ids),ctypes.byref(used)):
    return dict(state='unknown',reason='enumeration_failed',win32=ctypes.get_last_error())
   if used.value<ctypes.sizeof(ids):
    present=pid in ids[:used.value//ctypes.sizeof(ctypes.c_ulong)]
    return dict(state='unknown' if present else 'dead',reason='open_failed_present' if present else 'pid_absent',win32=opening_error,exit_code=None)
  return dict(state='unknown',reason='enumeration_capacity',win32=opening_error)
 try:
  times=[ctypes.c_ulonglong() for _ in range(4)]
  if not K.GetProcessTimes(h,*[ctypes.byref(t) for t in times]):return dict(state='unknown',reason='creation_failed',win32=ctypes.get_last_error())
  if times[0].value!=expected_created:
   return dict(state='replaced',reason='creation_mismatch',actual_created=times[0].value,exit_code=None)
  waited=K.WaitForSingleObject(h,0)
  if waited==258:return dict(state='live',reason='same_process_live')
  if waited!=0:return dict(state='unknown',reason='wait_failed',win32=ctypes.get_last_error())
  code=ctypes.c_ulong();ok=K.GetExitCodeProcess(h,ctypes.byref(code))
  return dict(state='dead',reason='same_process_signaled',exit_code=code.value if ok else None)
 finally:K.CloseHandle(h)
