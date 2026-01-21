import argparse
import os

from playwright.sync_api import sync_playwright

import config


SITE_MAP = {
    "facebook": ("auth_profile", "https://www.facebook.com/"),
    "x": ("auth_profile_x", "https://x.com/login"),
    "linkedin": ("auth_profile_linkedin", "https://www.linkedin.com/login"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Abre un navegador persistente para iniciar sesión manualmente")
    parser.add_argument(
        "--site",
        choices=sorted(SITE_MAP.keys()),
        default="facebook",
        help="Servicio a autenticar (usa 'x' para Twitter/X)",
    )
    parser.add_argument(
        "--channel",
        default=config.X_BROWSER_CHANNEL or None,
        help="Canal del navegador (por ejemplo 'chrome') si quieres usar Chrome del sistema",
    )
    parser.add_argument(
        "--profile-path",
        default=None,
        help="Ruta al directorio de datos de usuario de Chrome/Chromium",
    )
    parser.add_argument(
        "--profile-directory",
        default=config.X_PROFILE_DIRECTORY or None,
        help="Nombre del perfil dentro de user-data-dir (ej. 'Profile 6')",
    )
    return parser.parse_args()


def manual_login(
    site: str,
    channel: str | None,
    profile_path: str | None,
    profile_directory: str | None,
) -> None:
    profile_dir, start_url = SITE_MAP[site]
    
    # Determinar ruta del perfil
    if profile_path:
        user_data_dir = profile_path
    elif site == "x" and config.X_PROFILE_PATH:
        # Solo usar config.X_PROFILE_PATH si estamos en X
        user_data_dir = config.X_PROFILE_PATH
    else:
        # Por defecto usar el directorio del mapa (ej. auth_profile_linkedin)
        user_data_dir = os.path.join(os.getcwd(), profile_dir)

    os.makedirs(user_data_dir, exist_ok=True)

    profile_info = user_data_dir
    if profile_path and profile_directory:
        profile_info = os.path.join(user_data_dir, profile_directory)

    print(f"Abriendo Chromium en modo manual para {site.upper()} usando perfil: {profile_info}")
    print("Completa el inicio de sesión en la ventana. Cierra el navegador cuando termines.")

    launch_kwargs = {
        "user_data_dir": user_data_dir,
        "headless": False,
        "args": [
            "--start-maximized",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-features=FedCm,FederatedCredentialManagement,PrivacySandboxAdsApis",
        ],
        "viewport": None,
    }
    if channel:
        launch_kwargs["channel"] = channel
    if profile_path and profile_directory:
        launch_kwargs["args"].append(f"--profile-directory={profile_directory}")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(**launch_kwargs)

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(start_url)

        try:
            page.wait_for_timeout(9999999)
        except Exception:
            print("Navegador cerrado. Perfil guardado si el login fue exitoso.")


if __name__ == "__main__":
    args = parse_args()
    manual_login(args.site, args.channel, args.profile_path, args.profile_directory)
