"""ShopMate — Streamlit chat interface with image upload."""

import os

import streamlit as st
from dotenv import load_dotenv

from agent.client import ShopMateAgent

load_dotenv()

st.set_page_config(page_title="ShopMate", page_icon="🛒")
st.title("🛒 ShopMate")
st.caption("Tell me what you're looking for, or upload a photo of a product.")

api_key = os.environ.get("GROQ_API_KEY")
if not api_key or api_key == "your-key-here":
    st.error("Set GROQ_API_KEY in .env before using ShopMate.")
    st.stop()

if "agent" not in st.session_state:
    st.session_state.agent = ShopMateAgent(api_key=api_key)
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "display_history" not in st.session_state:
    st.session_state.display_history = []

for turn in st.session_state.display_history:
    with st.chat_message(turn["role"]):
        if turn.get("image"):
            st.image(turn["image"], width=200)
        st.markdown(turn["text"])

uploaded_image = st.file_uploader("Upload a product photo (optional)", type=["png", "jpg", "jpeg"])
user_text = st.chat_input("What are you looking for?")

if user_text:
    image_arg = None
    if uploaded_image is not None:
        image_bytes = uploaded_image.getvalue()
        media_type = uploaded_image.type or "image/png"
        image_arg = (image_bytes, media_type)

    st.session_state.display_history.append({
        "role": "user",
        "text": user_text,
        "image": uploaded_image.getvalue() if uploaded_image is not None else None,
    })
    with st.chat_message("user"):
        if uploaded_image is not None:
            st.image(uploaded_image, width=200)
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply_text, updated_history = st.session_state.agent.run_turn(
                st.session_state.conversation_history, user_text, image_arg
            )
        st.markdown(reply_text)

    st.session_state.conversation_history = updated_history
    st.session_state.display_history.append({"role": "assistant", "text": reply_text, "image": None})
