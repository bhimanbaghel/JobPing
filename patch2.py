import os

def patch_file():
    with open("frontend/src/views/WelcomeView.vue", "r", encoding="utf-8") as f:
        lines = f.readlines()
    for idx, l in enumerate(lines):
        if '<div class="hero-glow-line" aria-hidden="true" />' in l:
            lines.insert(idx+3, '        <!-- The "Coming Soon" section was removed here to prepare the WelcomeView for future feature toggles -->\n')
            break
    with open("frontend/src/views/WelcomeView.vue", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("WelcomeView.vue OK")

    with open("backend/app/blueprints/profile/routes.py", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find and modify profile routes
    for idx, l in enumerate(lines):
        if 'if pref is not None and pref.is_locked:' in l:
            lines.insert(idx, '    # Enforce the preferences confirmation lock: block modification if is_locked is set\n')
            break
        
    for idx, l in enumerate(lines):
        if 'companies = []' in l:
            if 'optional' not in lines[idx-1]:
                lines.insert(idx, '    # Companies are now optional; we collect any non-empty company inputs provided\n')
            break
            
    for idx, l in enumerate(lines):
        if 'is_locked_str = request.form.get("is_locked", "false").lower()' in l:
            if 'Check for is_locked form parameter\n' in lines[idx-1]:
                lines.pop(idx-1)
                idx -= 1
            lines.insert(idx, '    # Check for is_locked form parameter, applying the Preferences Confirmation Lock\n')
            break

    with open("backend/app/blueprints/profile/routes.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("profile/routes.py OK")

    with open("backend/app/blueprints/auth/routes.py", "r", encoding="utf-8") as f:
        lines = f.readlines()

    for idx, l in enumerate(lines):
        if 'if user.failed_login_attempts >= 5:' in l:
            lines.insert(idx, '    # Check if account is locked due to too many prior failed login attempts\n')
            break

    for idx, l in enumerate(lines):
        if 'if not check_password_hash(user.password_hash, password):' in l:
            lines.insert(idx, '    # Verify password against securely hashed NIST-validated password\n')
            break

    with open("backend/app/blueprints/auth/routes.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("auth/routes.py OK")

patch_file()
