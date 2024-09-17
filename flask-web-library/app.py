# Import Flask framework
from flask import Flask
# Tạo ngữ cảnh app
app = Flask('helloworldweb')
# Tạo route
@app.route('/hello', methods=['GET'])
def helloWorld():
 return 'This is a hello world page'
app.run(debug=False, host="0.0.0.0", port=1111, use_reloader=False)