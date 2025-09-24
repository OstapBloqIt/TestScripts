#include <stdio.h>
#include <SDL2/SDL.h>

int main(int argc, char* argv[]) {
    printf("=== SDL2 Debug Test Application ===\n");

    // Enable SDL2 logging
    SDL_LogSetAllPriority(SDL_LOG_PRIORITY_VERBOSE);

    // Initialize SDL2
    printf("Initializing SDL2...\n");
    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        printf("SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }

    // Print available video drivers
    printf("\nAvailable video drivers:\n");
    int num_drivers = SDL_GetNumVideoDrivers();
    for (int i = 0; i < num_drivers; i++) {
        printf("  %d: %s\n", i, SDL_GetVideoDriver(i));
    }

    // Print current video driver
    const char* current_driver = SDL_GetCurrentVideoDriver();
    printf("\nCurrent video driver: %s\n", current_driver ? current_driver : "NONE");

    // Get display info
    printf("\nDisplay information:\n");
    int num_displays = SDL_GetNumVideoDisplays();
    printf("  Number of displays: %d\n", num_displays);

    for (int i = 0; i < num_displays; i++) {
        SDL_DisplayMode mode;
        if (SDL_GetCurrentDisplayMode(i, &mode) == 0) {
            printf("  Display %d: %dx%d@%dHz, format=%s\n",
                   i, mode.w, mode.h, mode.refresh_rate,
                   SDL_GetPixelFormatName(mode.format));
        }
    }

    // Try to create a window
    printf("\nCreating window...\n");
    SDL_Window* window = SDL_CreateWindow(
        "SDL2 Test Window",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        800, 600,
        SDL_WINDOW_SHOWN
    );

    if (!window) {
        printf("SDL_CreateWindow failed: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }

    printf("Window created successfully!\n");

    // Create renderer
    printf("Creating renderer...\n");
    SDL_Renderer* renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (!renderer) {
        printf("SDL_CreateRenderer failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    printf("Renderer created successfully!\n");

    // Render a simple color pattern
    printf("Rendering test pattern...\n");

    // Red background
    SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255);
    SDL_RenderClear(renderer);

    // Green rectangle
    SDL_SetRenderDrawColor(renderer, 0, 255, 0, 255);
    SDL_Rect rect = {100, 100, 200, 150};
    SDL_RenderFillRect(renderer, &rect);

    // Blue rectangle
    SDL_SetRenderDrawColor(renderer, 0, 0, 255, 255);
    SDL_Rect rect2 = {400, 300, 200, 150};
    SDL_RenderFillRect(renderer, &rect2);

    SDL_RenderPresent(renderer);

    printf("Test pattern rendered. Display should show colored rectangles.\n");
    printf("Waiting 5 seconds...\n");

    SDL_Delay(5000);

    // Cleanup
    printf("Cleaning up...\n");
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();

    printf("SDL2 test completed successfully!\n");
    return 0;
}