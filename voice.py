
#Product Data
products = {
 "rice": {"price": 60, "stock": 20, "unit": "kg"},
 "sugar": {"price": 48, "stock": 15, "unit": "kg"},
 "milk": {"price": 30, "stock": 25, "unit": "packet"},
 "tea": {"price": 120, "stock": 10, "unit": "pack"},
 "soap": {"price": 35, "stock": 30, "unit": "piece"}
}


shop_timings = "The shop is open from 8 AM to 9 PM."
cart = []

#To find products
def find_product(message):
 for product in products:
   if product in message:
    return product
 return None

def respond(message):
    message = message.lower()
    if "hello" in message or "hi" in message:
        return "Hello! How can I help you today?"
    if "timing" in message or "open" in message or "close" in message:
        return shop_timings

    product = find_product(message)

    if "price" in message and product:
        item = products[product]
        return f"{product.title()} costs ₹{item['price']} per{item['unit']}."
    if ("available" in message or "have" in message or "stock" in message) and product:
        item = products[product]
        if item["stock"] > 0:
            return f"Yes, {product} is available. We have {item['stock']} {item['unit']} units."
        return f"Sorry, {product} is currently out of stock."

    if "add" in message and product:
        cart.append(product)
        return f"{product.title()} has been added to your cart."
    if "cart" in message or "total" in message:
        if not cart:
            return "Your cart is empty."
        total = sum(products[item]["price"] for item in cart)
        return f"Your cart contains {', '.join(cart)}. Total is ₹{total}."
    if "bye" in message or "exit" in message:
        return "Thank you for visiting. Goodbye!" 
    return "Sorry, I did not understand. Please ask about price,stock, cart, or shop timings."

while True:
    user_message = input("You: ")
    answer = respond(user_message)
    print("Assistant:", answer)
    if "bye" in user_message.lower() or "exit" in user_message.lower():
        break

import pyttsx3
engine = pyttsx3.init()
def speak(text):
    engine.say(text)
    engine.runAndWait()
      
speak(answer)

while True:
    user_message = input("You: ")
    answer = respond(user_message)
    print("Assistant:", answer)
    speak(answer)
    if "bye" in user_message.lower() or "exit" in user_message.lower():
        break


import speech_recognition as sr
recognizer = sr.Recognizer()
def listen():
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio)
        print("You said:", text)
        return text.lower()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""
user_message = listen()

#Main loop
while True:
    user_message = listen()
    if not user_message:
        answer = "Sorry, I could not hear you clearly. Please try again."
        print("Assistant:", answer)
        speak(answer)
        continue

    answer = respond(user_message)
    print("Assistant:", answer)
    speak(answer)
    if "bye" in user_message or "exit" in user_message:
        break