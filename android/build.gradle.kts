plugins {
    id("com.android.library") version "8.2.2"
    id("maven-publish")
    signing
    id("com.gradleup.nmcp") version "0.0.8"
}

android {
    namespace = "io.github.project_minigraf.minigraf"
    compileSdk = 34
    defaultConfig {
        minSdk = 24
        targetSdk = 34
    }
    sourceSets {
        getByName("main") {
            jniLibs.srcDirs("jniLibs")
            java.srcDirs("src/main/java")
        }
    }
    publishing {
        singleVariant("release")
    }
}

afterEvaluate {
    publishing {
        publications {
            create<MavenPublication>("release") {
                from(components["release"])
                groupId = "io.github.project-minigraf"
                artifactId = "minigraf-android"
                version = System.getenv("RELEASE_VERSION") ?: "0.0.0-local"

                pom {
                    name.set("Minigraf Android")
                    description.set("Zero-config, single-file, embedded graph database with bi-temporal Datalog queries — Android bindings")
                    url.set("https://github.com/project-minigraf/minigraf-android")
                    licenses {
                        license {
                            name.set("MIT OR Apache-2.0")
                            url.set("https://github.com/project-minigraf/minigraf-android/blob/main/LICENSE-MIT")
                        }
                    }
                    developers {
                        developer {
                            id.set("adityamukho")
                            name.set("Aditya Mukhopadhyay")
                        }
                    }
                    scm {
                        connection.set("scm:git:git://github.com/project-minigraf/minigraf-android.git")
                        developerConnection.set("scm:git:ssh://github.com/project-minigraf/minigraf-android.git")
                        url.set("https://github.com/project-minigraf/minigraf-android")
                    }
                }
            }
        }
    }

    signing {
        val signingKey = System.getenv("GPG_SIGNING_KEY")
        val signingPassword = System.getenv("GPG_SIGNING_PASSWORD")
        if (signingKey != null && signingPassword != null) {
            useInMemoryPgpKeys(signingKey, signingPassword)
            sign(publishing.publications["release"])
        }
    }
}

nmcp {
    publish("release") {
        username = System.getenv("CENTRAL_TOKEN_USERNAME") ?: ""
        password = System.getenv("CENTRAL_TOKEN_PASSWORD") ?: ""
        publicationType = "AUTOMATIC"
    }
}
