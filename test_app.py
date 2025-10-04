import streamlit as st

st.title("🧪 Test App")
st.write("This is a minimal test app to verify Streamlit Cloud deployment.")
st.success("If you can see this message, the deployment is working!")

# Basic functionality test
if st.button("Test Button"):
    st.balloons()
    st.write("✅ Button click successful!")

st.info("Repository: kentaro-seki/company_inner_search_app")
st.info("Branch: main")
st.info("Main file: test_app.py")
