import streamlit as st
st.title('안녕하세요!')
st.subheader('블라블라블라~')
st.write('http://naver.com')
st.link_button('네이버~','http://naver.com')

st.info('hello!')
st.error('hello!')
st.warning('hello!')
st.success('hello!')

name = st.text_input('이름을 입력해주세요 : ')
if st.button('환영인사'):
    st.write(name+'님 안녕하세요')
    st.balloons()
    st.image("https://img.freepik.com/premium-photo/charming-dynamic-3d-render-little-cat-with-playful-nature-white-background-generative_68880-3617.jpg")
