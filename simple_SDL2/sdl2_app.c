#include <stdio.h>
#include <stdbool.h>
#include <SDL2/SDL.h>

#define WINDOW_WIDTH 800
#define WINDOW_HEIGHT 600

typedef struct {
    SDL_Window* window;
    SDL_Renderer* renderer;
    bool running;
} App;

bool init_app(App* app) {
    // Force Wayland driver for embedded systems
    if (SDL_SetHint(SDL_HINT_VIDEODRIVER, "wayland") == SDL_FALSE) {
        printf("Warning: Could not set video driver hint\n");
    }

    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        printf("SDL_Init failed: %s\n", SDL_GetError());
        return false;
    }

    printf("Using video driver: %s\n", SDL_GetCurrentVideoDriver());

    app->window = SDL_CreateWindow(
        "Simple SDL2 App - iMX8M Mini",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE
    );

    if (!app->window) {
        printf("SDL_CreateWindow failed: %s\n", SDL_GetError());
        SDL_Quit();
        return false;
    }

    app->renderer = SDL_CreateRenderer(app->window, -1, SDL_RENDERER_ACCELERATED);
    if (!app->renderer) {
        printf("SDL_CreateRenderer failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(app->window);
        SDL_Quit();
        return false;
    }

    app->running = true;
    return true;
}

void handle_events(App* app) {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        switch (event.type) {
            case SDL_QUIT:
                app->running = false;
                break;
            case SDL_KEYDOWN:
                if (event.key.keysym.sym == SDLK_ESCAPE) {
                    app->running = false;
                }
                break;
        }
    }
}

void render(App* app) {
    static Uint32 start_time = 0;
    if (start_time == 0) start_time = SDL_GetTicks();

    Uint32 current_time = SDL_GetTicks();
    float time_factor = (current_time - start_time) / 1000.0f;

    // Animated background color
    Uint8 red = (Uint8)(128 + 127 * sin(time_factor));
    Uint8 green = (Uint8)(128 + 127 * sin(time_factor + 2.0f));
    Uint8 blue = (Uint8)(128 + 127 * sin(time_factor + 4.0f));

    SDL_SetRenderDrawColor(app->renderer, red, green, blue, 255);
    SDL_RenderClear(app->renderer);

    // Draw animated rectangle
    int rect_size = 100 + (int)(50 * sin(time_factor * 2));
    SDL_Rect animated_rect = {
        WINDOW_WIDTH/2 - rect_size/2,
        WINDOW_HEIGHT/2 - rect_size/2,
        rect_size,
        rect_size
    };

    SDL_SetRenderDrawColor(app->renderer, 255, 255, 255, 255);
    SDL_RenderFillRect(app->renderer, &animated_rect);

    SDL_RenderPresent(app->renderer);
}

void cleanup(App* app) {
    if (app->renderer) {
        SDL_DestroyRenderer(app->renderer);
    }
    if (app->window) {
        SDL_DestroyWindow(app->window);
    }
    SDL_Quit();
}

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;

    App app = {0};

    printf("Starting SDL2 application on iMX8M Mini with Weston...\n");

    if (!init_app(&app)) {
        return 1;
    }

    printf("Application initialized successfully!\n");
    printf("Press ESC or close window to exit.\n");

    while (app.running) {
        handle_events(&app);
        render(&app);
        SDL_Delay(16); // ~60 FPS
    }

    cleanup(&app);
    printf("Application terminated.\n");

    return 0;
}