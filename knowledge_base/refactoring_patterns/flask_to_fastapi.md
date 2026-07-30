# Flask to FastAPI Migration Pattern

## Context
Flask monolithic applications use `@app.route()` decorators with manual request/response handling. FastAPI modernizes this with automatic validation, type hints, and OpenAPI documentation.

## Transformation Rules
1. `@app.route('/path', methods=['GET'])` → `@app.get('/path')`
2. `request.get_json()` → Pydantic `BaseModel` parameter
3. `jsonify({...})` → Direct dict/model return
4. `return {...}, 404` → `raise HTTPException(status_code=404)`
5. Direct DB access → `Depends(get_db)` dependency injection

## Example
```python
# BEFORE (Flask)
@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = db.session.query(User).get(user_id)
    if not user:
        return {'error': 'Not found'}, 404
    return jsonify(user.to_dict()), 200

# AFTER (FastAPI)
@app.get('/api/users/{user_id}', response_model=UserSchema)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user
```

## Anti-patterns to Avoid
- Don't use `dict` as request body type — use Pydantic models
- Don't catch generic `Exception` without re-raising `HTTPException`
- Don't use global database connections — use dependency injection
