package imgui_example_sdl2_metal

#assert(ODIN_OS == .Darwin)

// WARNING:
// Not only have I not tested this as I don't own an Apple device, I have also
// never written ObjC in my life!
// This may very well work, but it also definitely might not.

// This is an example of using the bindings with SDL2 and Metal
// For a more complete example with comments, see:
// https://github.com/ocornut/imgui/blob/master/examples/example_sdl2_metal/main.mm

USE_DOCKING_AND_VIEWPORTS :: true

import "../../imgui/"

import sdl "vendor:sdl2"
import MTL "vendor:darwin/Metal"
import CA "vendor:darwin/QuartzCore"
import NS "vendor:darwin/Foundation"

main :: proc() {
	imgui.CHECKVERSION()
	imgui.CreateContext(nil)
	defer imgui.DestroyContext(nil)
	io := imgui.GetIO()
	io.ConfigFlags += {.NavEnableKeyboard, .NavEnableGamepad}
	when USE_DOCKING_AND_VIEWPORTS {
		io.ConfigFlags += {.DockingEnable}
		io.ConfigFlags += {.ViewportsEnable}
	}

	imgui.StyleColorsDark(nil)

	if .ViewportsEnable in io.ConfigFlags {
		style := imgui.GetStyle()
		style.WindowRounding = 0
		style.Colors[imgui.Col.WindowBg].w =1
	}

	assert(sdl.Init(sdl.INIT_EVERYTHING) == 0)
	defer sdl.Quit()

	sdl.SetHint(sdl.HINT_RENDER_DRIVER, "metal")

	window := sdl.CreateWindow(
		"Dear ImGui SDL2+Metal example",
		sdl.WINDOWPOS_CENTERED,
		sdl.WINDOWPOS_CENTERED,
		1280, 720,
		{.RESIZABLE, .ALLOW_HIGHDPI})
	assert(window != nil)
	defer sdl.DestroyWindow(window)

	renderer := sdl.CreateRenderer(window, -1, {.ACCELERATED, .PRESENTVSYNC})
	defer sdl.DestroyRenderer(renderer)
	assert(renderer != nil)

	layer := cast(^CA.MetalLayer)sdl.RenderGetMetalLayer(renderer)
	layer->setPixelFormat(.BGRA8Unorm)

	imgui.ImGui_ImplMetal_Init(layer->device())
	defer imgui.ImGui_ImplMetal_Shutdown()
	imgui.ImGui_ImplSDL2_InitForMetal(window)
	defer imgui.ImGui_ImplSDL2_Shutdown()

	command_queue := layer->device()->newCommandQueue()
	render_pass_descriptor :^MTL.RenderPassDescriptor= MTL.RenderPassDescriptor.alloc()->init()

	running := true
	for running {
		e: sdl.Event
		for sdl.PollEvent(&e) {
			imgui.ImGui_ImplSDL2_ProcessEvent(&e)

			#partial switch e.type {
			case .QUIT: running = false
			}
		}

		width, height: i32
		sdl.GetRendererOutputSize(renderer, &width, &height)
		layer->setDrawableSize(NS.Size{ NS.Float(width), NS.Float(height) })
		drawable := layer->nextDrawable()

		command_buffer := command_queue->commandBuffer()
		render_pass_descriptor->colorAttachments()->object(0)->setClearColor(MTL.ClearColor{ 0, 0, 0, 1 })
		render_pass_descriptor->colorAttachments()->object(0)->setTexture(drawable->texture())
		render_pass_descriptor->colorAttachments()->object(0)->setLoadAction(.Clear)
		render_pass_descriptor->colorAttachments()->object(0)->setStoreAction(.Store)

		render_encoder := command_buffer->renderCommandEncoderWithDescriptor(render_pass_descriptor)
		defer render_encoder->endEncoding()

		imgui.ImGui_ImplMetal_NewFrame(render_pass_descriptor)
		imgui.ImGui_ImplSDL2_NewFrame()
		imgui.NewFrame()

		imgui.ShowDemoWindow(nil)

		if imgui.Begin("Window containing a quit button", nil, {}) {
			if imgui.Button("The quit button in question") {
				running = false
			}
		}
		imgui.End()

		imgui.Render()
		imgui.ImGui_ImplMetal_RenderDrawData(imgui.GetDrawData(), command_buffer, render_encoder)

		if .ViewportsEnable in io.ConfigFlags {
			imgui.UpdatePlatformWindows()
			imgui.RenderPlatformWindowsDefault()
		}

		command_buffer->presentDrawable(drawable)
		command_buffer->commit()
	}
}
