// Consumer test project: an app that depends on minigraf-android only through
// its Maven coordinates, as a user's app does. See run.sh.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

val minigrafRepo: String? = providers.gradleProperty("minigrafRepo").orNull

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        if (minigrafRepo != null) {
            // Local mode: minigraf-android comes only from the built artifacts,
            // never from Maven Central, even if that version is already there.
            exclusiveContent {
                forRepository { maven { url = uri(minigrafRepo) } }
                filter { includeGroup("io.github.project-minigraf") }
            }
        }
        google()
        mavenCentral()
    }
}

rootProject.name = "minigraf-android-consumer"
