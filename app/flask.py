from flask import Flask, render_template, request

app = Flask(__name__)

print("hi there")

@app.route('/')
def hello():
    return 'Hello, World!'


# @app.route('/')
# def form():
#     return render_template('form.html')
#
#
# @app.route('/app', methods=['POST', 'GET'])
# def data():
#     if request.method == 'GET':
#         return f"The URL /data is accessed directly. Try going to '/form' to submit form"
#     if request.method == 'POST':
#         form_data = request.form
#         print("hello i am here")
#         print(form_data)
#
#         return render_template('data.html', form_data=form_data)


app.run(host='0.0.0.0', port=5000)