# BDIScoin GUI

# Development

Start server
```console
$ cd gui-web
$ source venv/scripts/activate
$ python app.py
```

Start frontend
```console
$ cd gui-web/frontend
$ npm run dev
```

# Deployment

```console
$ cd gui-web/frontend
$ npm run build
```

1. Copy the `frontend/dist/static` folder to `static`
2. Update `templates/index.html` with the info in `frontend/dist/index.html`
