plugins {
    id("com.android.application") version "8.2.2"
    id("org.jetbrains.kotlin.android") version "2.0.21"
}

val minigrafVersion: String = providers.gradleProperty("minigrafVersion").get()

android {
    namespace = "io.github.project_minigraf.consumer"
    compileSdk = 34
    defaultConfig {
        applicationId = "io.github.project_minigraf.consumer"
        minSdk = 24
        targetSdk = 34
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    sourceSets {
        getByName("androidTest") {
            java.srcDirs("tests")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("io.github.project-minigraf:minigraf-android:$minigrafVersion")
    androidTestImplementation("androidx.test:runner:1.5.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
}
