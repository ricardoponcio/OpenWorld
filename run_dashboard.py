from web.dashboard import app

if __name__ == "__main__":
    print("Iniciando Dashboard OpenWorld...")
    app.run(debug=True, host='0.0.0.0', port=5000)
