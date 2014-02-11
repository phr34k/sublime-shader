Integrated GLSL Syntax Highlighting, Validation, Build-steps for Sublime Text 2.

This work is based on GLSL Syntax Highlighting for Sublime Text 2 (https://github.com/euler0/sublime-glsl)
and GL Shader Validator (https://github.com/WebGLTools/GL-Shader-Validator), released under the Appache v2 
license. It recognizes files with the extension *.frag;*.vert;*.tess;*.eval;*.shader

Usage:

In the Packages folder, create a folder named 'Shader', and extract the contents of the repository in there.

Syntax for *.shader:

In the case of file with the suffix *.shader, this is a conglomerate of the various shaders using standard preprocessor techniques.
A preview of the syntax for this is below.

#ifdef _GLSL_

#version 140   

	#ifdef _VERTEX_
	//vertex stuff here
	#endif

	#ifdef _TESS_CONTROL_
	//tesselation control stuff here
	#endif

	#ifdef _TESS_EVAL_
	//tesselation evaluation stuff here
	#endif

	#ifdef _FRAGMENT_
	//fragment stuff here
	#endif

#endif