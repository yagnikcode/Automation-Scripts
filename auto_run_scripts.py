import os
import subprocess

def run_scripts(script_list):
    for script in script_list:
        arg = script + '_python_test'
        script = script + '.py'
        if os.path.isfile(script) and script.endswith('.py'):
            print(f'Running: {script} with argument: {arg}')
            try:
                # Execute the script with the provided argument
                result = subprocess.run(['python', script, arg], capture_output=True, text=True)

                # Print the output and errors, if any
                print(result.stdout)
                if result.stderr:
                    print(f"Error in {script}:\n{result.stderr}")

            except Exception as e:
                print(f"Failed to run {script}: {e}")
        else:
            print(f'Skipping: {script} (not found or not a Python file)')


scripts_to_run = ['resale_details' , 'nfa_data']
run_scripts(scripts_to_run)


