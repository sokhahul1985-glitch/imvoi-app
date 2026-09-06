import subprocess
import time
import json
import urllib.request
import asyncio
import websockets

async def main():
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    proc = subprocess.Popen([
        edge_path,
        "--headless=new",
        "--remote-debugging-port=9225",
        "--disable-gpu",
        "--no-sandbox",
        "about:blank"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        await asyncio.sleep(2)
        with urllib.request.urlopen("http://127.0.0.1:9225/json/list") as resp:
            targets = json.loads(resp.read().decode())
        
        page_target = next(t for t in targets if t.get('type') == 'page')
        ws_url = page_target['webSocketDebuggerUrl']
        
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await ws.send(json.dumps({"id": 2, "method": "Log.enable"}))
            await ws.send(json.dumps({
                "id": 3,
                "method": "Page.navigate",
                "params": {"url": "http://127.0.0.1:8080/index.html"}
            }))

            await asyncio.sleep(3)

            # Test execution of key button actions
            actions = [
                ("Init AutoRent", "typeof window.initAutoRentSystem === 'function' && (window.initAutoRentSystem(), true)"),
                ("Switch to Bookings Tab", "window.switchTab('bookings'); true"),
                ("Switch to Cars Tab", "window.switchTab('cars'); true"),
                ("Switch to Customers Tab", "window.switchTab('customers'); true"),
                ("Switch to Calendar Tab", "window.switchTab('calendar'); true"),
                ("Switch to Telegram Tab", "window.switchTab('telegram'); true"),
                ("Switch to Settings Tab", "window.switchTab('settings'); true"),
                ("Switch to Dashboard Tab", "window.switchTab('dashboard'); true"),
                ("Open New Booking Modal", "window.openNewBookingModal(); true"),
                ("Add Extra Car Slot", "window.addBookingModalExtraCarSlot(); true"),
                ("Close Booking Modal", "window.closeModal('bookingModal'); true"),
                ("Open New Customer Modal", "window.openNewCustomerModal(); true"),
                ("Close Customer Modal", "window.closeModal('customerModal'); true"),
                ("Open New Car Modal", "window.openNewCarModal(); true"),
                ("Close Car Modal", "window.closeModal('carModal'); true"),
                ("Select Category AutoRent", "window.selectQuoteCategoryTab('autorent', true); true"),
                ("Select Category Car", "window.selectQuoteCategoryTab('car', true); true"),
                ("Select Category VIP", "window.selectQuoteCategoryTab('vip', true); true"),
                ("Select Category Visa", "window.selectQuoteCategoryTab('visa', true); true"),
            ]

            results = []
            for name, expr in actions:
                await ws.send(json.dumps({
                    "id": 100,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr, "returnByValue": True}
                }))
                msg = await ws.recv()
                res = json.loads(msg).get('result', {})
                has_err = 'exceptionDetails' in res
                if has_err:
                    print(f"[FAIL] {name}: {res['exceptionDetails']}")
                    results.append((name, False, res['exceptionDetails']))
                else:
                    val = res.get('result', {}).get('value')
                    print(f"[PASS] {name}: OK ({val})")
                    results.append((name, True, val))

            print(f"\nSummary: {sum(1 for _, ok, _ in results if ok)}/{len(results)} passed!")

    finally:
        proc.terminate()
        proc.wait()

asyncio.run(main())
