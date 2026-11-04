plugins {
    id("com.android.application") version "8.2.2"
    id("org.jetbrains.kotlin.android") version "2.0.21"
}

android {
    namespace = "io.github.project_minigraf.benchmark"
    compileSdk = 34
    defaultConfig {
        applicationId = "io.github.project_minigraf.benchmark"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "839-source"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk { abiFilters += "arm64-v8a" }
    }
    // Measure optimized, non-debuggable application code. The local debug key
    // is only an installation key for this unpublished benchmark app.
    buildTypes {
        getByName("release") {
            isDebuggable = false
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    testBuildType = "release"
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation(files("libs/minigraf.aar"))
    implementation("net.java.dev.jna:jna:5.14.0@aar")
    androidTestImplementation("androidx.test:runner:1.5.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    testImplementation("junit:junit:4.13.2")
}
