import os

# Update WelcomeView.vue
welcome_view_path = "frontend/src/views/WelcomeView.vue"
with open(welcome_view_path, "r", encoding="utf-8") as f:
    content = f.read()
target_welcome = '          <div class="hero-glow-line" aria-hidden="true" />\n        </section>\n\n      </div>'
replacement_welcome = '          <div class="hero-glow-line" aria-hidden="true" />\n        </section>\n\n        <!-- The "Coming Soon" section was removed here to prepare the WelcomeView for future feature toggles -->\n      </div>'
if target_welcome in content:
    with open(welcome_view_path, "w", encoding="utf-8") as f:
        f.write(content.replace(target_welcome, replacement_welcome, 1))
    print("WelcomeView.vue updated.")

# Update profile/routes.py
profile_routes_path = "backend/app/blueprints/profile/routes.py"
with open(profile_routes_path, "r", encoding="utf-8") as f:
    content = f.read()

target_profile_1 = '''    pref = db.session.query(UserPreference).filter_by(user_id=uid).one_or_none()
    if pref is not None and pref.is_locked:'''
replacement_profile_1 = '''    pref = db.session.query(UserPreference).filter_by(user_id=uid).one_or_none()
    
    # Enforce the preferences confirmation lock: block modification if is_locked is set
    if pref is not None and pref.is_locked:'''

target_profile_2 = '''    companies = []
    for c in request.form.getlist("companies"):
        if isinstance(c, str):'''
replacement_profile_2 = '''    # Companies are now optional; we collect any non-empty company inputs provided
    companies = []
    for c in request.form.getlist("companies"):
        if isinstance(c, str):'''

target_profile_3 = '''    # Check for is_locked form parameter
    is_locked_str = request.form.get("is_locked", "false").lower()'''
replacement_profile_3 = '''    # Check for is_locked form parameter, applying the Preferences Confirmation Lock
    is_locked_str = request.form.get("is_locked", "false").lower()'''

if target_profile_1 in content and target_profile_2 in content and target_profile_3 in content:
    content = content.replace(target_profile_1, replacement_profile_1, 1)
    content = content.replace(target_profile_2, replacement_profile_2, 1)
    content = content.replace(target_profile_3, replacement_profile_3, 1)
    with open(profile_routes_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("profile/routes.py updated.")

