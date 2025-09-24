CC = gcc
CFLAGS = -Wall -Wextra -std=c99
INCLUDES = -I/usr/local/include
LDFLAGS = -L/usr/lib/aarch64-linux-gnu
LIBS = -lSDL2 -lm

SRCDIR = .
SOURCES = sdl2_app.c
OBJECTS = $(SOURCES:.c=.o)
TARGET = sdl2_app

.PHONY: all clean test debug

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(OBJECTS) $(LDFLAGS) $(LIBS) -o $(TARGET)

%.o: %.c
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

test: $(TARGET)
	@echo "Running SDL2 application..."
	./$(TARGET)

debug: CFLAGS += -g -DDEBUG
debug: $(TARGET)

clean:
	rm -f $(OBJECTS) $(TARGET) sdl2_test

install-deps:
	@echo "SDL2 dependencies are already installed"
	@echo "Available video drivers: wayland, KMSDRM, x11, offscreen, dummy"

help:
	@echo "Available targets:"
	@echo "  all       - Build the SDL2 application"
	@echo "  test      - Build and run the application"
	@echo "  debug     - Build with debug symbols"
	@echo "  clean     - Clean build files"
	@echo "  help      - Show this help"