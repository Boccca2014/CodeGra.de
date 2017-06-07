#!/usr/bin/env python3
from psef import app
from flask import jsonify


@app.route("/api/hello")
def say_hello():
    return jsonify({"msg": "Hello this is Flask."})


@app.route("/api/code/<id>")
def get_code(id):
    print(id)
    if id == "0":
        return jsonify({
            "id": 0,
            "lang": "python",
            "code": "def id0func0():\n\treturn 0\n\n\ndef id0func1():\n\treturn 1",
            "feedback": {
                "0": "wtf",
            }
        })
    else:
        return jsonify({
            "id": id,
            "lang": "c",
            "code": "void\nsome_func(void) {}\n\nvoid other_func(int x) {\n\treturn 2 * x;\n}",
            "feedback": {
                "1": "slechte naam voor functie",
                "3": "niet veel beter..."
            }
        })
