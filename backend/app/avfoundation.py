"""Dependency-free macOS camera metadata, using the Objective-C runtime.

Run in a disposable subprocess: device discovery may block in system drivers.
Enumeration matches OpenCV AVFoundation: video and muxed devices sorted by unique ID.
No session is opened and no permission is requested here.
"""

import ctypes as c
import json


def opencv_camera_order(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Match OpenCV CAP_AVFOUNDATION cameraNum: sort by AVCaptureDevice.uniqueID.

    OpenCV combines video and muxed devices, then sorts the entire list by
    uniqueID before indexing. Enumeration order from macOS isn't the capture
    index. Never guess an index from an unsorted list: the wrong physical
    camera could be opened when a virtual camera was selected.
    """
    ordered = sorted(rows, key=lambda item: str(item["device_id"]))
    return [{**item, "index": index} for index, item in enumerate(ordered)]


def devices() -> list[dict]:
    c.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
    av = c.CDLL("/System/Library/Frameworks/AVFoundation.framework/AVFoundation")
    objc = c.CDLL("/usr/lib/libobjc.A.dylib")
    objc.objc_getClass.argtypes = [c.c_char_p]
    objc.objc_getClass.restype = c.c_void_p
    objc.sel_registerName.argtypes = [c.c_char_p]
    objc.sel_registerName.restype = c.c_void_p

    def send(receiver, selector, *args, result=c.c_void_p):
        signature = c.CFUNCTYPE(result, c.c_void_p, c.c_void_p, *[t for t, _ in args])
        call = signature(("objc_msgSend", objc))
        return call(receiver, objc.sel_registerName(selector.encode()), *[v for _, v in args])

    def string(receiver, selector):
        value = send(receiver, selector)
        raw = send(value, "UTF8String", result=c.c_char_p) if value else None
        return raw.decode("utf-8") if raw else ""

    pool = send(send(objc.objc_getClass(b"NSAutoreleasePool"), "alloc"), "init")
    try:
        device_class = objc.objc_getClass(b"AVCaptureDevice")
        rows: list[dict[str, object]] = []
        for media in ("AVMediaTypeVideo", "AVMediaTypeMuxed"):
            array = send(
                device_class, "devicesWithMediaType:", (c.c_void_p, c.c_void_p.in_dll(av, media))
            )
            for index in range(send(array, "count", result=c.c_ulong)):
                device = send(array, "objectAtIndex:", (c.c_ulong, index))
                rows.append(
                    {
                        "index": len(rows),
                        "name": string(device, "localizedName")[:160],
                        "device_id": string(device, "uniqueID"),
                        "device_type": string(device, "deviceType"),
                    }
                )
        return opencv_camera_order(rows)
    finally:
        send(pool, "drain", result=None)


if __name__ == "__main__":
    print(json.dumps(devices()))
