
from .parameters import *
from .payload_util import parse_order_details
import json

def unwrap(kwargs):
    if "kwargs" in kwargs and isinstance(kwargs["kwargs"], dict):
        kwargs = kwargs["kwargs"]
    return kwargs

def create_order(client, kwargs):

    kwargs = unwrap(kwargs)
    validated = CreateOrderParameters(**json.loads(kwargs))
    order_payload = parse_order_details(validated.model_dump())
    
    order_uri = "/v2/checkout/orders"
    response = client.post(uri=order_uri, payload=order_payload)
    return json.dumps(response)



def capture_order(client, kwargs):
    validated = CaptureOrderParameters(**json.loads(kwargs))
    order_capture_uri = f"/v2/checkout/orders/{validated.order_id}/capture"
    result = client.post(uri=order_capture_uri, payload=None)
    status = result.get("status")
    amount = result.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])[0].get("amount", {}).get("value")
    currency = result.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])[0].get("amount", {}).get("currency_code")

    return json.dumps({
        "message": f"The PayPal order {validated.order_id} has been successfully captured.",
        "status": status,
        "amount": f"{currency} {amount}" if amount and currency else "N/A",
        "raw": result 
    })


def get_order_details(client, kwargs):
    validated = OrderIdParameters(**json.loads(kwargs))
    order_get_uri = f"/v2/checkout/orders/{validated.order_id}"
    
    result = client.get(order_get_uri)
    status = result.get("status")
    amount = result.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])[0].get("amount", {}).get("value")
    currency = result.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])[0].get("amount", {}).get("currency_code")

    return json.dumps({
        "message": f"The PayPal order {validated.order_id} has been successfully captured.",
        "status": status,
        "amount": f"{currency} {amount}" if amount and currency else "N/A",
        "raw": result 
    })