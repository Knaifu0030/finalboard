"""Backend API testing for The Last Billboard.

Tests all user stories systematically against the public endpoint.
"""
import requests
import hmac
import hashlib
import json
import time
from datetime import datetime

BASE_URL = "https://final-billboard.preview.emergentagent.com/api"
ADMIN_PASSWORD = "Kaneki1#"
OLD_ADMIN_PASSWORD = "paste-over-it"

# From backend/.env
RAZORPAY_KEY_SECRET = "gSUL8WXzLx7yCyJYeV6YhCMT"

class TestRunner:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []
        
    def test(self, name, condition, detail=""):
        """Run a single test assertion"""
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"✅ {name}")
            return True
        else:
            print(f"❌ {name}")
            if detail:
                print(f"   Detail: {detail}")
            self.failures.append({"test": name, "detail": str(detail)})
            return False
    
    def summary(self):
        """Print test summary"""
        print(f"\n{'='*70}")
        print(f"Tests: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\nFailed tests:")
            for f in self.failures:
                print(f"  - {f['test']}")
                if f['detail']:
                    print(f"    {f['detail']}")
        print(f"{'='*70}")
        return len(self.failures) == 0


def compute_razorpay_signature(order_id, payment_id):
    """Compute HMAC-SHA256 signature for Razorpay payment verification"""
    body = f"{order_id}|{payment_id}"
    return hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


def test_user_story_2_get_wall(t):
    """USER STORY 2: GET /api/wall returns expected structure"""
    print("\n[USER STORY 2] GET /api/wall")
    
    try:
        r = requests.get(f"{BASE_URL}/wall", timeout=10)
        t.test("GET /api/wall returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code != 200:
            return
        
        data = r.json()
        
        # Check structure
        t.test("Response has 'current' field", "current" in data)
        t.test("Response has 'behind' field", "behind" in data)
        t.test("Response has 'recent' field", "recent" in data)
        t.test("Response has 'price' field", "price" in data)
        t.test("Response has 'clock' field", "clock" in data)
        t.test("Response has 'frozen' field", "frozen" in data)
        t.test("Response has 'takeovers' field", "takeovers" in data)
        t.test("Response has 'total_paid_label' field", "total_paid_label" in data)
        t.test("Response has 'pending' field", "pending" in data)
        t.test("Response has 'razorpay_ready' field", "razorpay_ready" in data)
        
        # Check price structure
        if "price" in data:
            price = data["price"]
            t.test("Price has current_paise", "current_paise" in price)
            t.test("Price has next_paise", "next_paise" in price)
            t.test("Price has next_label", "next_label" in price)
            t.test("Price has unit_paise", "unit_paise" in price)
            
            # Verify price ladder: next = current + 4400 paise ($0.50)
            if "current_paise" in price and "next_paise" in price:
                current = price["current_paise"]
                next_p = price["next_paise"]
                expected_next = current + 4400
                t.test(
                    "Next price = current + 4400 paise ($0.50)",
                    next_p == expected_next,
                    f"current={current}, next={next_p}, expected={expected_next}"
                )
        
        # Check clock structure
        if "clock" in data:
            clock = data["clock"]
            t.test("Clock has paused field", "paused" in clock)
            t.test("Clock has ends_at field", "ends_at" in clock)
            t.test("Clock has server_now field", "server_now" in clock)
        
        # Check behind array (max 3)
        if "behind" in data:
            t.test("Behind array has max 3 items", len(data["behind"]) <= 3, f"Got {len(data['behind'])}")
        
        # Check recent array (max 10, excluding current)
        if "recent" in data:
            t.test("Recent array has max 10 items", len(data["recent"]) <= 10, f"Got {len(data['recent'])}")
        
        return data
        
    except Exception as e:
        t.test("GET /api/wall succeeds", False, str(e))
        return None


def test_user_story_3_create_order(t, wall_data):
    """USER STORY 3: POST /api/create-order price ladder enforcement"""
    print("\n[USER STORY 3] POST /api/create-order price ladder")
    
    if not wall_data or "price" not in wall_data:
        print("⚠️  Skipping: no wall data")
        return None
    
    next_paise = wall_data["price"]["next_paise"]
    current_email = wall_data.get("current", {}).get("email") if wall_data.get("current") else None
    
    # Test (a): amount below next_paise must return 409
    try:
        below_amount = next_paise - 100
        r = requests.post(f"{BASE_URL}/create-order", json={
            "text": "test below minimum",
            "name": "tester",
            "email": "test@example.com",
            "amount_paise": below_amount
        }, timeout=10)
        
        t.test(
            "Below minimum returns 409",
            r.status_code == 409,
            f"Got {r.status_code}"
        )
        
        if r.status_code == 409:
            t.test(
                "Below minimum error message exact",
                r.json().get("detail") == "Someone already paid more than that.",
                f"Got: {r.json().get('detail')}"
            )
    except Exception as e:
        t.test("Below minimum test", False, str(e))
    
    # Test (b): valid amount returns order details
    try:
        r = requests.post(f"{BASE_URL}/create-order", json={
            "text": "valid test order",
            "name": "tester",
            "email": "tester@example.com",
            "amount_paise": next_paise
        }, timeout=15)
        
        t.test("Valid amount returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            t.test("Response has mode field", "mode" in data)
            
            if data.get("mode") == "checkout":
                t.test("Checkout mode has order_id", "order_id" in data)
                t.test("Checkout mode has key_id", "key_id" in data)
                t.test("Checkout mode has amount_paise", "amount_paise" in data)
                
                if "order_id" in data:
                    t.test(
                        "Order ID starts with 'order_'",
                        data["order_id"].startswith("order_"),
                        f"Got: {data['order_id']}"
                    )
                
                return data
    except Exception as e:
        t.test("Valid amount test", False, str(e))
    
    # Test (c): using current holder's email must return 409
    if current_email:
        try:
            r = requests.post(f"{BASE_URL}/create-order", json={
                "text": "self dethrone attempt",
                "name": "current holder",
                "email": current_email,
                "amount_paise": next_paise
            }, timeout=10)
            
            t.test(
                "Current holder email returns 409",
                r.status_code == 409,
                f"Got {r.status_code}"
            )
        except Exception as e:
            t.test("Self-dethrone test", False, str(e))
    
    # Test (d): invalid email returns 400
    try:
        r = requests.post(f"{BASE_URL}/create-order", json={
            "text": "invalid email test",
            "name": "tester",
            "email": "not-an-email",
            "amount_paise": next_paise
        }, timeout=10)
        
        t.test("Invalid email returns 400", r.status_code == 400, f"Got {r.status_code}")
    except Exception as e:
        t.test("Invalid email test", False, str(e))
    
    # Test (e): image_url without http:// returns 400
    try:
        r = requests.post(f"{BASE_URL}/create-order", json={
            "text": "bad image url",
            "name": "tester",
            "email": "test@example.com",
            "image_url": "not-a-url.com/image.png",
            "amount_paise": next_paise
        }, timeout=10)
        
        t.test("Image URL without http returns 400", r.status_code == 400, f"Got {r.status_code}")
    except Exception as e:
        t.test("Invalid image URL test", False, str(e))
    
    return None


def test_user_story_4_moderation(t, wall_data):
    """USER STORY 4: AI moderation via POST /api/moderate"""
    print("\n[USER STORY 4] AI Moderation")
    
    if not wall_data or "price" not in wall_data:
        print("⚠️  Skipping: no wall data")
        return
    
    next_paise = wall_data["price"]["next_paise"]
    
    # Messages that MUST be BLOCKED (422 with exact error)
    block_cases = [
        "Swiggy's delivery is garbage, use anything else",
        "XYZ Coffee is a scam, they water the milk",
        "i am Nike. just do it.",
        "i will find you and kill you"
    ]
    
    # Messages that MUST be ALLOWED
    allow_cases = [
        "come to my cafe in bandra, best filter coffee",
        "i love Nike",
        "try my app, it turns receipts into spreadsheets",
        "marry me sarah",
        "hello"
    ]
    
    # Test BLOCK cases via create-order
    for msg in block_cases:
        try:
            r = requests.post(f"{BASE_URL}/create-order", json={
                "text": msg,
                "name": "tester",
                "email": f"test{hash(msg)}@example.com",
                "amount_paise": next_paise
            }, timeout=15)
            
            t.test(
                f"BLOCK: '{msg[:40]}...' returns 422",
                r.status_code == 422,
                f"Got {r.status_code}"
            )
            
            if r.status_code == 422:
                t.test(
                    f"BLOCK error message exact for '{msg[:30]}'",
                    r.json().get("detail") == "The wall has standards. Barely, but it has them.",
                    f"Got: {r.json().get('detail')}"
                )
        except Exception as e:
            t.test(f"BLOCK test for '{msg[:30]}'", False, str(e))
    
    # Test ALLOW cases via /api/moderate endpoint
    for msg in allow_cases:
        try:
            r = requests.post(f"{BASE_URL}/moderate", json={
                "text": msg,
                "name": "tester"
            }, timeout=15)
            
            t.test(
                f"ALLOW: '{msg[:40]}...' returns 200",
                r.status_code == 200,
                f"Got {r.status_code}"
            )
            
            if r.status_code == 200:
                data = r.json()
                t.test(
                    f"ALLOW verdict for '{msg[:30]}'",
                    data.get("allow") == True,
                    f"Got allow={data.get('allow')}"
                )
        except Exception as e:
            t.test(f"ALLOW test for '{msg[:30]}'", False, str(e))


def test_user_story_5_payment_verification(t, wall_data):
    """USER STORY 5: Razorpay signature verification and takeover execution"""
    print("\n[USER STORY 5] Payment verification and takeover")
    
    if not wall_data or "price" not in wall_data:
        print("⚠️  Skipping: no wall data")
        return None
    
    next_paise = wall_data["price"]["next_paise"]
    
    # Create an order first
    try:
        r = requests.post(f"{BASE_URL}/create-order", json={
            "text": "payment verification test",
            "name": "verifier",
            "email": "verifier@example.com",
            "amount_paise": next_paise
        }, timeout=15)
        
        if r.status_code != 200:
            print(f"⚠️  Could not create order: {r.status_code}")
            return None
        
        order_data = r.json()
        
        if order_data.get("mode") != "checkout":
            print(f"⚠️  Order mode is {order_data.get('mode')}, not checkout")
            return None
        
        order_id = order_data.get("order_id")
        if not order_id:
            print("⚠️  No order_id in response")
            return None
        
        # Simulate a payment ID
        payment_id = f"pay_test_{int(time.time())}"
        
        # Compute correct signature
        correct_sig = compute_razorpay_signature(order_id, payment_id)
        
        # Test with correct signature
        r = requests.post(f"{BASE_URL}/verify-payment", json={
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": correct_sig
        }, timeout=15)
        
        t.test(
            "Correct signature returns 200",
            r.status_code == 200,
            f"Got {r.status_code}: {r.text[:200]}"
        )
        
        if r.status_code == 200:
            data = r.json()
            t.test("Response has ok=true", data.get("ok") == True)
            t.test("Response has message_id", "message_id" in data)
            
            message_id = data.get("message_id")
            
            # Wait a moment for AI processing
            time.sleep(2)
            
            # Verify the takeover happened
            r2 = requests.get(f"{BASE_URL}/wall", timeout=10)
            if r2.status_code == 200:
                new_wall = r2.json()
                current = new_wall.get("current")
                
                if current:
                    t.test(
                        "New message is current",
                        current.get("text") == "payment verification test",
                        f"Got: {current.get('text')}"
                    )
                    t.test("New message has ad_line", bool(current.get("ad_line")))
                    
                    # Check price ladder advanced
                    new_next = new_wall["price"]["next_paise"]
                    expected_new_next = next_paise + 4400
                    t.test(
                        "Price ladder advanced by $0.50",
                        new_next == expected_new_next,
                        f"Expected {expected_new_next}, got {new_next}"
                    )
                
                # Check if previous message has heckle/obituary
                if "recent" in new_wall and len(new_wall["recent"]) > 0:
                    prev = new_wall["recent"][0]
                    if prev.get("ended_at"):
                        t.test("Previous message has ended_at", True)
                        t.test("Previous message has heckle", bool(prev.get("heckle")))
                        t.test("Previous message has obituary", bool(prev.get("obituary")))
                        t.test("Previous message has dethroned_by", bool(prev.get("dethroned_by")))
            
            # Test wrong signature
            wrong_sig = correct_sig[:-1] + ("0" if correct_sig[-1] != "0" else "1")
            r3 = requests.post(f"{BASE_URL}/verify-payment", json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": wrong_sig
            }, timeout=10)
            
            t.test(
                "Wrong signature returns 400",
                r3.status_code == 400,
                f"Got {r3.status_code}"
            )
            
            if r3.status_code == 400:
                t.test(
                    "Wrong signature error message",
                    r3.json().get("detail") == "That payment does not check out.",
                    f"Got: {r3.json().get('detail')}"
                )
            
            # Test idempotency - replay same verify call
            r4 = requests.post(f"{BASE_URL}/verify-payment", json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": correct_sig
            }, timeout=10)
            
            t.test(
                "Replay returns 200 (idempotent)",
                r4.status_code == 200,
                f"Got {r4.status_code}"
            )
            
            if r4.status_code == 200:
                t.test("Replay has already=true", r4.json().get("already") == True)
            
            return message_id
            
    except Exception as e:
        t.test("Payment verification test", False, str(e))
        return None


def test_user_story_6_pending_state(t, wall_data):
    """USER STORY 6: PENDING rail state"""
    print("\n[USER STORY 6] PENDING state")
    
    if not wall_data or "price" not in wall_data:
        print("⚠️  Skipping: no wall data")
        return
    
    next_paise = wall_data["price"]["next_paise"]
    
    # Create an order but don't verify payment
    try:
        r = requests.post(f"{BASE_URL}/create-order", json={
            "text": "pending state test",
            "name": "pendinger",
            "email": "pending@example.com",
            "amount_paise": next_paise
        }, timeout=15)
        
        if r.status_code != 200:
            print(f"⚠️  Could not create order: {r.status_code}")
            return
        
        order_data = r.json()
        
        # Immediately check wall state
        r2 = requests.get(f"{BASE_URL}/wall", timeout=10)
        
        if r2.status_code == 200:
            data = r2.json()
            pending = data.get("pending")
            
            t.test("Wall has pending field", pending is not None)
            
            if pending:
                t.test("Pending has name", "name" in pending)
                t.test("Pending has amount_label", "amount_label" in pending)
                t.test("Pending has status", "status" in pending)
                t.test(
                    "Pending status is 'created'",
                    pending.get("status") == "created",
                    f"Got: {pending.get('status')}"
                )
                t.test(
                    "Pending name matches",
                    pending.get("name") == "pendinger",
                    f"Got: {pending.get('name')}"
                )
    except Exception as e:
        t.test("PENDING state test", False, str(e))


def test_user_story_9_messages_endpoint(t):
    """USER STORY 9: GET /api/messages with sorting"""
    print("\n[USER STORY 9] GET /api/messages sorting")
    
    try:
        # Test sort by reign
        r = requests.get(f"{BASE_URL}/messages?sort=reign", timeout=10)
        t.test("GET /api/messages?sort=reign returns 200", r.status_code == 200)
        
        if r.status_code == 200:
            data = r.json()
            t.test("Response has messages array", "messages" in data)
            
            if "messages" in data and len(data["messages"]) > 1:
                # Verify descending reign_seconds order
                reigns = [m.get("reign_seconds", 0) for m in data["messages"]]
                is_descending = all(reigns[i] >= reigns[i+1] for i in range(len(reigns)-1))
                t.test("Messages sorted by reign (descending)", is_descending, f"Reigns: {reigns[:5]}")
        
        # Test sort by price
        r2 = requests.get(f"{BASE_URL}/messages?sort=price", timeout=10)
        t.test("GET /api/messages?sort=price returns 200", r2.status_code == 200)
        
        if r2.status_code == 200:
            data2 = r2.json()
            
            if "messages" in data2 and len(data2["messages"]) > 1:
                # Verify descending amount_paise order
                prices = [m.get("amount_paise", 0) for m in data2["messages"]]
                is_descending = all(prices[i] >= prices[i+1] for i in range(len(prices)-1))
                t.test("Messages sorted by price (descending)", is_descending, f"Prices: {prices[:5]}")
    
    except Exception as e:
        t.test("Messages endpoint test", False, str(e))


def test_user_story_10_admin(t):
    """USER STORY 10: Admin endpoints"""
    print("\n[USER STORY 10] Admin endpoints")
    
    # Test admin login with OLD password (should fail)
    try:
        r = requests.post(f"{BASE_URL}/admin/login", json={
            "password": OLD_ADMIN_PASSWORD
        }, timeout=10)
        
        t.test("OLD admin password 'paste-over-it' returns 401", r.status_code == 401, f"Got {r.status_code}")
    except Exception as e:
        t.test("OLD admin password test", False, str(e))
    
    # Test admin login with wrong password
    try:
        r = requests.post(f"{BASE_URL}/admin/login", json={
            "password": "wrong-password"
        }, timeout=10)
        
        t.test("Wrong admin password returns 401", r.status_code == 401, f"Got {r.status_code}")
    except Exception as e:
        t.test("Wrong admin password test", False, str(e))
    
    # Test admin login with NEW correct password
    try:
        r = requests.post(f"{BASE_URL}/admin/login", json={
            "password": ADMIN_PASSWORD
        }, timeout=10)
        
        t.test("NEW admin password 'Kaneki1#' returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            t.test("Admin login response has ok=true", data.get("ok") == True)
    except Exception as e:
        t.test("NEW admin password test", False, str(e))
    
    # Test admin state endpoint
    try:
        r = requests.get(
            f"{BASE_URL}/admin/state",
            headers={"X-Admin-Password": ADMIN_PASSWORD},
            timeout=10
        )
        
        t.test("GET /admin/state returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            t.test("Admin state has 'state' field", "state" in data)
            t.test("Admin state has 'pending' field", "pending" in data)
            t.test("Admin state has 'outbox' field", "outbox" in data)
            t.test("Admin state has 'messages' field", "messages" in data)
            
            # Check outbox for dethrone emails
            if "outbox" in data and len(data["outbox"]) > 0:
                has_dethrone = any(
                    o.get("subject") == "You were dethroned."
                    for o in data["outbox"]
                )
                t.test("Outbox contains dethrone emails", has_dethrone)
                
                # Check email body
                dethrone_email = next(
                    (o for o in data["outbox"] if o.get("subject") == "You were dethroned."),
                    None
                )
                if dethrone_email:
                    body = dethrone_email.get("body", "")
                    t.test(
                        "Dethrone email body contains 'Paste over it for'",
                        "Paste over it for" in body,
                        f"Body preview: {body[:100]}"
                    )
    except Exception as e:
        t.test("Admin state test", False, str(e))
    
    # Test admin takeover (seed)
    try:
        r = requests.post(
            f"{BASE_URL}/admin/takeover",
            headers={"X-Admin-Password": ADMIN_PASSWORD},
            json={
                "text": "admin seeded message",
                "name": "admin",
                "email": "admin@test.com"
            },
            timeout=15
        )
        
        t.test("Admin takeover returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            t.test("Admin takeover has ok=true", data.get("ok") == True)
            t.test("Admin takeover has message_id", "message_id" in data)
    except Exception as e:
        t.test("Admin takeover test", False, str(e))
    
    # Test admin pause/unpause
    try:
        # Get current state
        r = requests.get(
            f"{BASE_URL}/admin/state",
            headers={"X-Admin-Password": ADMIN_PASSWORD},
            timeout=10
        )
        
        if r.status_code == 200:
            current_paused = r.json()["state"]["clock"]["paused"]
            
            # Toggle pause
            r2 = requests.post(
                f"{BASE_URL}/admin/pause",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"paused": not current_paused},
                timeout=10
            )
            
            t.test("Admin pause toggle returns 200", r2.status_code == 200, f"Got {r2.status_code}")
            
            if r2.status_code == 200:
                data = r2.json()
                t.test("Pause response has paused field", "paused" in data)
                t.test("Pause response has ends_at field", "ends_at" in data)
            
            # Restore original state
            requests.post(
                f"{BASE_URL}/admin/pause",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"paused": current_paused},
                timeout=10
            )
    except Exception as e:
        t.test("Admin pause test", False, str(e))


def test_user_story_11_frozen_state(t):
    """USER STORY 11: Frozen / FINAL HOLDER end state"""
    print("\n[USER STORY 11] Frozen state (will restore after)")
    
    try:
        # Set clock to expire very soon
        r = requests.post(
            f"{BASE_URL}/admin/clock",
            headers={"X-Admin-Password": ADMIN_PASSWORD},
            json={"hours": 0.0001},
            timeout=10
        )
        
        t.test("Set clock to 0.0001 hours returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code != 200:
            return
        
        # Wait for expiry loop to run (~25 seconds)
        print("   Waiting 25s for expiry loop...")
        time.sleep(25)
        
        # Check if wall is frozen
        r2 = requests.get(f"{BASE_URL}/wall", timeout=10)
        
        if r2.status_code == 200:
            data = r2.json()
            t.test("Wall is frozen", data.get("frozen") == True, f"frozen={data.get('frozen')}")
            
            if data.get("current"):
                t.test(
                    "Current message is_final=true",
                    data["current"].get("is_final") == True,
                    f"is_final={data['current'].get('is_final')}"
                )
        
        # Try to create order on frozen wall
        r3 = requests.post(f"{BASE_URL}/create-order", json={
            "text": "frozen wall test",
            "name": "tester",
            "email": "frozen@example.com",
            "amount_paise": 10000
        }, timeout=10)
        
        t.test("Create order on frozen wall returns 409", r3.status_code == 409, f"Got {r3.status_code}")
        
        if r3.status_code == 409:
            t.test(
                "Frozen wall error message",
                r3.json().get("detail") == "The wall is closed.",
                f"Got: {r3.json().get('detail')}"
            )
        
        # RESTORE: Set clock back to 48 hours and pause
        print("   Restoring wall state...")
        r4 = requests.post(
            f"{BASE_URL}/admin/clock",
            headers={"X-Admin-Password": ADMIN_PASSWORD},
            json={"hours": 48},
            timeout=10
        )
        
        t.test("Restore clock to 48 hours returns 200", r4.status_code == 200)
        
        r5 = requests.post(
            f"{BASE_URL}/admin/pause",
            headers={"X-Admin-Password": ADMIN_PASSWORD},
            json={"paused": True},
            timeout=10
        )
        
        t.test("Pause wall after restore returns 200", r5.status_code == 200)
        
        # Verify wall is unfrozen
        time.sleep(2)
        r6 = requests.get(f"{BASE_URL}/wall", timeout=10)
        if r6.status_code == 200:
            data = r6.json()
            t.test("Wall is unfrozen after restore", data.get("frozen") == False, f"frozen={data.get('frozen')}")
    
    except Exception as e:
        t.test("Frozen state test", False, str(e))
        
        # Try to restore anyway
        try:
            print("   Attempting emergency restore...")
            requests.post(
                f"{BASE_URL}/admin/clock",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"hours": 48},
                timeout=10
            )
            requests.post(
                f"{BASE_URL}/admin/pause",
                headers={"X-Admin-Password": ADMIN_PASSWORD},
                json={"paused": True},
                timeout=10
            )
        except:
            pass


def test_chat_endpoints(t):
    """NEW SESSION: Chat endpoints with moderation"""
    print("\n[CHAT] Chat endpoints")
    
    # Test GET /api/chat
    try:
        r = requests.get(f"{BASE_URL}/chat", timeout=10)
        t.test("GET /api/chat returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            t.test("Chat response has 'messages' field", "messages" in data)
            t.test("Chat response has 'count' field", "count" in data)
            
            if "messages" in data:
                t.test("Messages is an array", isinstance(data["messages"], list))
                
                # Check message structure if any exist
                if len(data["messages"]) > 0:
                    msg = data["messages"][0]
                    t.test("Message has 'id' field", "id" in msg)
                    t.test("Message has 'name' field", "name" in msg)
                    t.test("Message has 'text' field", "text" in msg)
                    t.test("Message has 'at' field", "at" in msg)
    except Exception as e:
        t.test("GET /api/chat test", False, str(e))
    
    # Test POST /api/chat with clean message
    try:
        clean_msg = f"this wall rules {int(time.time())}"
        r = requests.post(f"{BASE_URL}/chat", json={
            "name": "sam",
            "text": clean_msg
        }, timeout=15)
        
        t.test("POST /api/chat with clean message returns 200", r.status_code == 200, f"Got {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            t.test("Posted message has 'id' field", "id" in data)
            t.test("Posted message has 'name' field", "name" in data)
            t.test("Posted message has 'text' field", "text" in data)
            t.test("Posted message has 'at' field", "at" in data)
            t.test("Posted message name is 'sam'", data.get("name") == "sam", f"Got: {data.get('name')}")
            t.test("Posted message text matches", data.get("text") == clean_msg, f"Got: {data.get('text')}")
            
            # Verify message appears in GET /api/chat
            time.sleep(1)
            r2 = requests.get(f"{BASE_URL}/chat", timeout=10)
            if r2.status_code == 200:
                messages = r2.json().get("messages", [])
                found = any(m.get("text") == clean_msg for m in messages)
                t.test("Posted message appears in GET /api/chat", found)
    except Exception as e:
        t.test("POST /api/chat clean message test", False, str(e))
    
    # Test POST /api/chat with abusive message (should be blocked)
    try:
        r = requests.post(f"{BASE_URL}/chat", json={
            "name": "baduser",
            "text": "kill yourself"
        }, timeout=15)
        
        t.test("POST /api/chat with abusive message returns 422", r.status_code == 422, f"Got {r.status_code}")
        
        if r.status_code == 422:
            detail = r.json().get("detail", "")
            expected_msg = "Not on this wall. The wall has standards. Barely, but it has them."
            t.test(
                "Abusive message error is correct",
                detail == expected_msg,
                f"Got: {detail}"
            )
            
            # Verify message does NOT appear in GET /api/chat
            time.sleep(1)
            r2 = requests.get(f"{BASE_URL}/chat", timeout=10)
            if r2.status_code == 200:
                messages = r2.json().get("messages", [])
                found = any("kill yourself" in m.get("text", "") for m in messages)
                t.test("Abusive message NOT in GET /api/chat", not found)
    except Exception as e:
        t.test("POST /api/chat abusive message test", False, str(e))
    
    # Test POST /api/chat with empty text (should return 400)
    try:
        r = requests.post(f"{BASE_URL}/chat", json={
            "name": "tester",
            "text": ""
        }, timeout=10)
        
        t.test("POST /api/chat with empty text returns 400", r.status_code == 400, f"Got {r.status_code}")
    except Exception as e:
        t.test("POST /api/chat empty text test", False, str(e))
    
    # Test POST /api/chat with text over 140 chars (should be truncated)
    try:
        long_text = "a" * 150
        r = requests.post(f"{BASE_URL}/chat", json={
            "name": "tester",
            "text": long_text
        }, timeout=15)
        
        # Should either return 200 with truncated text or 422 if validation rejects
        if r.status_code == 200:
            data = r.json()
            t.test("Long text is truncated to 140 chars", len(data.get("text", "")) <= 140, f"Got length: {len(data.get('text', ''))}")
        else:
            t.test("Long text returns error or truncates", r.status_code in [200, 400, 422], f"Got {r.status_code}")
    except Exception as e:
        t.test("POST /api/chat long text test", False, str(e))


def main():
    print("="*70)
    print("THE LAST BILLBOARD - BACKEND API TESTS")
    print("="*70)
    
    t = TestRunner()
    
    # Run tests in order
    wall_data = test_user_story_2_get_wall(t)
    
    if wall_data:
        test_user_story_3_create_order(t, wall_data)
        test_user_story_4_moderation(t, wall_data)
        test_user_story_5_payment_verification(t, wall_data)
        test_user_story_6_pending_state(t, wall_data)
    
    test_user_story_9_messages_endpoint(t)
    test_user_story_10_admin(t)
    test_chat_endpoints(t)
    # test_user_story_11_frozen_state(t)  # Commented out to avoid disrupting the wall
    
    # Summary
    success = t.summary()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
