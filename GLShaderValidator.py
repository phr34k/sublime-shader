import sublime
import sublime_plugin
import re
import subprocess
import os
import threading
import time

class GLShaderError:
    """ Represents an error """
    region = None
    message = ''

    def __init__(self, region, message):
        self.region = region
        self.message = message


class GLIntermediateError:
    """ Represents an intermediate error """
    errorLine = None
    errorToken = None
    errorDescription = None
    errorLocation = None

    def __init__(self, errorLine, errorToken, errorDescription, errorLocation):
        self.errorLine = errorLine
        self.errorToken = errorToken    
        self.errorDescription = errorDescription
        self.errorLocation = errorLocation    



class ANGLECommandLine:
    """ Wrapper for ANGLE CLI """

    packagePath = "Shader"
    platform = sublime.platform()
    errorPattern = re.compile("^...*?:(\d+):0: ([^:]*): (.*)")
    permissionChecked = False
    ANGLEPath = {
        "osx": "./essl_to_glsl_osx",
        "linux": "./essl_to_glsl_linux",
        "windows": "shader.exe"
    }

    def ensure_script_permissions(self):
        """ Ensures that we have permission to execute the command """

        if not self.permissionChecked:
            os.chmod(sublime.packages_path() + os.sep + self.packagePath + os.sep + self.ANGLEPath[self.platform], 0o755)

        self.permissionChecked = True
        return self.permissionChecked

    def validate_contents(self, filename, fileLines, content):
        """ Validates the file contents using ANGLE """
        ANGLEPath = self.ANGLEPath[self.platform]
        errors = []


        print "run_validator_process_2"     

        if filename is None:
            filename = "";

        # Create a shell process for essl_to_glsl and pick
        # up its output directly
        ANGLEProcess = subprocess.Popen(
            ANGLEPath + ' "' + filename + '"',
            cwd=sublime.packages_path() + os.sep + self.packagePath + os.sep,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True)

        if ANGLEProcess.stdin is not None:
            ANGLEProcess.stdin.write(content);
            ANGLEProcess.stdin.close();

        if ANGLEProcess.stdout is not None:
            errlines = ANGLEProcess.stdout.readlines()

            # Go through each error, ignoring any comments
            for e in errlines: 

                e = e.decode("utf-8")

                # Check if there was a permission denied
                # error running the essl_to_glsl cmd

                if re.search("permission denied", str(e), flags=re.IGNORECASE):
                    sublime.error_message("GLShaderValidator: permission denied to use essl_to_glsl command")
                    return []

                # ignore ANGLE's comments
                if not re.search("^####", e):

                    # Break down the error using the regexp
                    errorDetails = self.errorPattern.match(e)

                    # For each match construct an error
                    # object to pass back
                    if errorDetails is not None:
                        errorLine = int(errorDetails.group(1)) - 1
                        errorToken = errorDetails.group(2)
                        errorDescription = errorDetails.group(3)
                        errorLocation = fileLines[errorLine]

                        # Record the intermediate error
                        errors.append(GLIntermediateError( 
                            errorLine, errorToken, errorDescription, errorLocation
                        ))                                            

        return errors


class GLShaderValidatorCommand(sublime_plugin.EventListener):
    """ Main Validator Class """
    ANGLECLI = ANGLECommandLine()
    errors = None
    loadedSettings = False
    pluginSettings = None

    # these are the default settings. They are overridden and
    # documented in the GLShaderValidator.sublime-settings file
    DEFAULT_SETTINGS = {
        "glsv_enabled": 1,
        "glsv_spec": 0
    }

    def __init__(self):
        """ Startup """
        # ensure that the script has permissions to run
        self.ANGLECLI.ensure_script_permissions()

    def clear_settings(self):
        """ Resets the settings value so we will overwrite on the next run """
        for window in sublime.windows():
            for view in window.views():
                if view.settings().get('glsv_configured') is not None:
                    view.settings().set('glsv_configured', None)

    def apply_settings(self, view):
        """ Applies the settings from the settings file """

        # load in the settings file
        if self.pluginSettings is None:
            self.pluginSettings = sublime.load_settings(__name__ + ".sublime-settings")
            self.pluginSettings.clear_on_change('glsv_validator')
            self.pluginSettings.add_on_change('glsv_validator', self.clear_settings)

        if view.settings().get('glsv_configured') is None:

            view.settings().set('glsv_configured', True)

            # Go through the default settings
            for setting in self.DEFAULT_SETTINGS:

                # set the value
                settingValue = self.DEFAULT_SETTINGS[setting]

                # check if the user has overwritten the value
                # and switch to that instead
                if self.pluginSettings.get(setting) is not None:
                    settingValue = self.pluginSettings.get(setting)

                view.settings().set(setting, settingValue)

    def clear_errors(self, view):
        """ Removes any errors """
        view.erase_regions('glshadervalidate_errors')

    def show_errors(self, view):
        """ Passes over the array of errors and adds outlines """

        # Go through the errors that came back
        errorRegions = []
        for error in self.errors:
            errorRegions.append(error.region)

        # Put an outline around each one and a dot on the line
        view.add_regions(
            'glshadervalidate_errors',
            errorRegions,
            'glshader_error',
            'dot',
            sublime.DRAW_OUTLINED
        )


    def is_glsl_or_essl(self, view):
        """ Checks that the file is GLSL or ESSL """
        syntax = view.settings().get('syntax')
        isShader = False
        if syntax is not None:
            isShader = re.search('GLSL|ESSL', syntax, flags=re.IGNORECASE) is not None
        return isShader

    def is_valid_file_ending(self, view):
        """ Checks that the file ending will work for ANGLE """    
        if view.file_name() is None:
            return True;
        isValidFileEnding = re.search('(frag|vert|tess|eval|geo|shader)$', view.file_name()) is not None
        return isValidFileEnding

    def on_selection_modified(self, view):
        """ Shows a status message for an error region """
        view.erase_status('glshadervalidator')
        # If we have errors just locate the first one and go with that for the status
        if self.is_glsl_or_essl(view) and self.errors is not None:
            for sel in view.sel():
                for error in self.errors:
                    if error.region.contains(sel):
                        view.set_status('glshadervalidator', error.message)
                        return                        

    def on_load(self, view):
        """ File loaded """
        if self.is_glsl_or_essl(view) :
            view.mychanges = False;
            self.run_validator(view);                    

    def on_activated(self, view):
        """ File activated """           

    def on_post_save(self, view):
        """ File saved """    
        if self.is_glsl_or_essl(view) :
            view.mychanges = False;
            self.run_validator(view); 

    def on_modified(self, view):    
        """ File saved """    
        if self.is_glsl_or_essl(view) :
            view.mychanges = True;
            self.run_validator( view )





    

    def run_validator(self, view):
        exampleThread = ExampleThread(self, view)
        exampleThread.start()




class ExampleThread(threading.Thread):

    def __init__(self, cmd, edit):
        cmd.apply_settings(edit);
        threading.Thread.__init__(self)
        self.cmd = cmd
        self.edit = edit     
        self.fileLines = None
        self.content = None


        # early return if they have disabled the linter
        if self.edit.settings().get('glsv_enabled') == 0:
            self.edit.erase_status('glshadervalidator')
            self.cmd.clear_errors(self.edit)
            return

        # early return for anything not syntax highlighted as GLSL / ESSL
        if not self.cmd.is_glsl_or_essl(self.edit):
            self.edit.erase_status('glshadervalidator')
            self.cmd.clear_errors(self.edit);            
            return        
        
        # check for valid file endings.
        if self.cmd.is_valid_file_ending(self.edit):  
            self.edit.erase_status('glshadervalidator')
        else:            
            self.edit.set_status('glshadervalidator', "File name must end in .frag or .vert or .shader")
            self.cmd.clear_errors(self.edit);
            return;

        # Get the file lines and other information to run the thread.
        self.fileLines = self.edit.lines(sublime.Region(0, self.edit.size()))
        self.content = self.edit.substr( sublime.Region(0, self.edit.size()))           
        self.filename = self.edit.file_name();
        self.errors = [];

    def run(self):        
        if self.fileLines is None or self.content is None:             
            sublime.set_timeout(self.callback, 1)
            return;
        self.errors = self.cmd.ANGLECLI.validate_contents(self.filename, self.fileLines, self.content);        
        sublime.set_timeout(self.callback, 1)

    def callback(self):
        """self.cmd.view.insert(self.edit, 0, "Hello, World!")"""
        
        # Convert the GLImediateError to GLShaderError, uses heurestics to find the best location for the error result.
        errors = [];
        for error in self.errors:            
            errorLine = error.errorLine;
            errorToken = error.errorToken;
            errorDescription = error.errorDescription;
            errorLocation = error.errorLocation;
            if len(errorToken) > 0:
                betterLocation = self.edit.find( errorToken, errorLocation.begin(),  sublime.LITERAL)
                if betterLocation is not None:
                    errorLocation = betterLocation
            errors.append(GLShaderError( errorLocation, errorDescription ))

        # update the error list
        # self.cmd.clear_errors(self.edit);
        self.cmd.errors = errors;
        self.cmd.show_errors(self.edit);

        # invalidate the the status text near the selection.
        self.cmd.on_selection_modified(self.edit);