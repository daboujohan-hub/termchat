# LABO IA & TERMUX ACADEMY — Règles ProGuard
# Garder le WebView et le bridge JS fonctionnels après minification

# Garder les classes WebView
-keepclassmembers class ci.laboia.academy.MainActivity$AndroidBridge {
   public *;
}

# Garder les annotations JavascriptInterface (indispensable !)
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# AndroidX / AppCompat
-keep class androidx.** { *; }
-keep interface androidx.** { *; }
-dontwarn androidx.**

# WebKit
-keep class androidx.webkit.** { *; }

# Empêcher l'obfuscation des classes Activity
-keep public class * extends android.app.Activity
-keep public class * extends androidx.appcompat.app.AppCompatActivity

# Garder les noms de ressources
-keepclassmembers class **.R$* {
    public static <fields>;
}

# Logs supprimés en production (optionnel, sécurité)
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
}

-dontwarn java.lang.invoke**
-dontwarn javax.annotation.**
