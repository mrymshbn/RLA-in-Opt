"""

PortPy generates optimal fluences for IMRT plans that are compatible with the Eclipse system. This compatibility enables users to import the PortPy plan into the FDA-approved Eclipse system for a final clinical evaluation and comparisons with benchmark plans. This example outlines the following steps:


1. Creating a simple IMRT plan (Plan class, Optimization class)

2. Importing the PortPy plan into the Eclipse system for final leaf sequesing and dose calculation (Utils class)

3. Exporting the finally calculated dose from the Eclipse system (in DICOM RT-Dose format) into PortPy (Utils class)

4. Addressing the issue of dose discrepancy and demonstrating the correction steps to mitigate it

5. Comparing the PortPy plan against the benchmark IMRT plan for validation and analysis


"""

import portpy.photon as pp
import os
import matplotlib.pyplot as plt


''' 1) Creating a simple IMRT plan (Plan class, Optimization class)
'''


# specify the patient data location.
data_dir = r'../data'
# Use PortPy DataExplorer class to explore PortPy data
data = pp.DataExplorer(data_dir=data_dir)
# Pick a patient
data.patient_id = 'Lung_Patient_2'
# Load ct, structure set, beams for the above patient using CT, Structures, and Beams classes
ct = pp.CT(data)
structs = pp.Structures(data)
beams = pp.Beams(data)
# Pick a protocol
protocol_name = 'Lung_2Gy_30Fx'
# Load clinical criteria for a specified protocol
clinical_criteria = pp.ClinicalCriteria(data, protocol_name=protocol_name)

# Load hyper-parameter values for optimization problem for a specified protocol
opt_params = data.load_config_opt_params(protocol_name=protocol_name)
# Create optimization structures (i.e., Rinds)
structs.create_opt_structures(opt_params=opt_params)
# Load influence matrix
inf_matrix = pp.InfluenceMatrix(ct=ct, structs=structs, beams=beams)

# Create a plan using ct, structures, beams and influence matrix, and clinical criteria
my_plan = pp.Plan(ct=ct, structs=structs, beams=beams, inf_matrix=inf_matrix, clinical_criteria=clinical_criteria)

# Create cvxpy problem using the clinical criteria and optimization parameters
opt = pp.Optimization(my_plan, opt_params=opt_params, clinical_criteria=clinical_criteria)
opt.create_cvxpy_problem()
# Solve the cvxpy problem using Mosek
sol = opt.solve(solver='MOSEK', verbose=False)


'''2) Importing the PortPy plan into the Eclipse system

The method get_eclipse_fluence() stores the optimal fluence for each beam in a text file that can be imported into the Eclipse system. Please follow these steps to proceed:

1- Import the patient's data into the Eclipse system. This includes CT images and RT structures that are not included in the PortPy dataset and need to be downloaded from the [TCIA website](https://www.cancerimagingarchive.net/access-data/). 
The user can obtain the "TCIA collection ID" and "TCIA subject ID" using DataExplorer.get_tcia_metadata() method in PortPy. 

2- Create beams identical to those used during the optimization. If you used the default beams, you could import the benchmark IMRT plan (DICOM RT-Plan) provided in the PortPy dataset. PortPy uses the same beams as those in the benchmark IMRT plan by default.

3- Within the Eclipse system, right-click on each field and choose 'Import Optimal Fluence', as demonstrated in the figure below. Select the optimal fluence text file generated by PortPy for each field.

4- Finally, in Eclipse, execute the final leaf sequencing and dose calculation.

.'''

# get corresponding tcia patient metadata using data explorer object and download CT, RTSTRUCT from TCIA patient database for the below subject id and collection id
data.get_tcia_metadata()
# Generate and save the optimal fluence in a format compatible with the Eclipse system
pp.get_eclipse_fluence(my_plan=my_plan, sol=sol, path=os.path.join(r'C:\temp', data.patient_id))


''' 3)  Exporting the finally calculated dose from the Eclipse system into PortPy

After the final dose calculation in Eclipse, export the dose in DICOM RT-Dose format using the Eclipse Export module. 
Then, utilize the following lines of code to convert the exported dose into the PortPy format for visualization or evaluation purposes
'''

# Specify the location and name of the DICOM RT Dose file
dose_file_name = os.path.join(r'C:\temp', data.patient_id, 'rt_dose.dcm')
# Convert the DICOM dose into PortPy format
ecl_dose_3d = pp.convert_dose_rt_dicom_to_portpy(my_plan=my_plan, dose_file_name=dose_file_name)
ecl_dose_1d = inf_matrix.dose_3d_to_1d(dose_3d=ecl_dose_3d)

'''4)  Addressing the issue of dose discrepancy using the correction steps'''

# *** Large Dose Discrepancy: Observed when using the truncated sparse influence matrix **
# Visualize the DVH discrepancy between sparse and full
dose_sparse_1d = inf_matrix.A @ (sol['optimal_intensity'] * my_plan.get_num_of_fractions())
struct_names = ['PTV', 'ESOPHAGUS', 'HEART', 'CORD']
fig, ax = plt.subplots(figsize=(12, 8))
ax = pp.Visualization.plot_dvh(my_plan, dose_1d=ecl_dose_1d, struct_names=struct_names, style='solid', ax=ax, norm_flag=True)
ax = pp.Visualization.plot_dvh(my_plan, dose_1d=dose_sparse_1d, struct_names=struct_names, style='dotted', ax=ax, norm_flag=True)
ax.set_title('- Eclipse dose    .. PortPy dose using Sparse influence matrix')
ax.set_xlim(0, 85)
plt.show()

# ** Small Dose Discrepancy: Observed when using the full dense influence matrix **
# load full influence matrix to calculate dose using full matrix
beams_full = pp.Beams(data, load_inf_matrix_full=True)
# load influence matrix based upon beams and structure set
inf_matrix_full = pp.InfluenceMatrix(ct=ct, structs=structs, beams=beams_full, is_full=True)
dose_full_1d = inf_matrix_full.A @ (sol['optimal_intensity'] * my_plan.get_num_of_fractions()) # calculate dose using full matrix

# Visualize the DVH discrepancy between eclipse dose and dose using full matrix in portpy
struct_names = ['PTV', 'ESOPHAGUS', 'HEART', 'CORD']
fig, ax = plt.subplots(figsize=(12, 8))
ax = pp.Visualization.plot_dvh(my_plan, dose_1d=dose_full_1d, struct_names=struct_names, style='solid', ax=ax, norm_flag=True)
ax = pp.Visualization.plot_dvh(my_plan, dose_1d=ecl_dose_1d, struct_names=struct_names, style='dotted', ax=ax, norm_flag=True)
ax.set_title('- optimization(Using full matrix) .. Eclipse')
plt.show()


# ** Dose Correction **

# calculating delta
# normalize both the dose to PTV:V(100%) = 90%
norm_volume = 90
norm_struct = 'PTV'
pres = my_plan.get_prescription()

norm_factor_sparse = pp.Evaluation.get_dose(sol, dose_1d=dose_sparse_1d, struct=norm_struct, volume_per=norm_volume) / pres
dose_sparse_1d_norm = dose_sparse_1d / norm_factor_sparse

norm_factor_full = pp.Evaluation.get_dose(sol, dose_1d=dose_full_1d, struct=norm_struct, volume_per=norm_volume) / pres
dose_full_1d_norm = dose_full_1d / norm_factor_full

delta = (dose_full_1d_norm - dose_sparse_1d_norm)/my_plan.get_num_of_fractions()


# Building up the correction model. It is the same opitmization problem but with delta(correction term) in objective and constraints
# get opt params for optimization
old_delta = delta
num_corr = 2
for i in range(num_corr):

    A = inf_matrix.A
    opt = pp.Optimization(my_plan, opt_params=opt_params)
    x = opt.vars['x']
    opt.create_cvxpy_problem_correction(delta=delta)
    sol_corr = opt.solve(solver='MOSEK', verbose=False)
    
    dose_sparse_corr_1d = (inf_matrix.A @ sol_corr['optimal_intensity'] + delta) * my_plan.get_num_of_fractions()
    dose_full_corr_1d = inf_matrix_full.A @ (sol_corr['optimal_intensity'] * my_plan.get_num_of_fractions())
    
    # recalculate delta
    norm_volume = 90
    norm_struct = 'PTV'
    pres = my_plan.get_prescription()

    norm_factor_sparse = pp.Evaluation.get_dose(sol, dose_1d=dose_sparse_corr_1d, struct=norm_struct, volume_per=norm_volume) / pres
    dose_sparse_corr_1d_norm = dose_sparse_corr_1d / norm_factor_sparse

    norm_factor_full = pp.Evaluation.get_dose(sol, dose_1d=dose_full_corr_1d, struct=norm_struct, volume_per=norm_volume) / pres
    dose_full_corr_1d_norm = dose_full_corr_1d / norm_factor_full

    delta = (dose_full_corr_1d_norm - dose_sparse_corr_1d_norm)/my_plan.get_num_of_fractions()
    
    # Visualize DVH in correction step
    struct_names = ['PTV', 'ESOPHAGUS', 'HEART', 'CORD']
    fig, ax = plt.subplots(figsize=(12, 8))
    ax = pp.Visualization.plot_dvh(my_plan, dose_1d=dose_sparse_corr_1d, struct_names=struct_names, style='dotted', ax=ax, norm_flag=True)
    # ax = pp.Visualization.plot_dvh(my_plan, sol=sol_corr, struct_names=struct_names, style='solid', ax=ax, norm_flag=True)
    ax = pp.Visualization.plot_dvh(my_plan, dose_1d=dose_full_corr_1d, struct_names=struct_names, style='solid', ax=ax, norm_flag=True)
    ax.set_title('- Full dose .. Sparse dose')
    plt.show()
    delta = old_delta + delta
    old_delta = delta


# It can ben seen using above dvh plot that the discrepancy between sparse and full dose calculation has been reduced after 2 correction optimization loop. Users can modify 'num_corr' to modify the number of correction loop to get optimized dose similar to eclipse dose
# Repeat above steps of importing fluence to eclipse, perform final dose calculation import the dose back to portpy
# save fluence using correction optimization
pp.get_eclipse_fluence(my_plan=my_plan, sol=sol_corr, path=os.path.join(r'C:\temp', data.patient_id))
# Export corrected dose in dicom format from eclipse and specify it below
dose_file_name = os.path.join(r'C:\temp', data.patient_id, 'rt_dose_corr.dcm')  # Use need to modify the file name accordingly
ecl_dose_3d_corr = pp.convert_dose_rt_dicom_to_portpy(my_plan=my_plan, dose_file_name=dose_file_name)
ecl_dose_1d_corr = inf_matrix.dose_3d_to_1d(dose_3d=ecl_dose_3d_corr)


# compare dvh of our optimized porptpy plan with final plan in eclipse we got above)
struct_names = ['PTV', 'ESOPHAGUS', 'HEART', 'CORD', 'LUNG_L','LUNG_R']
fig, ax = plt.subplots(figsize=(12, 8))
ax = pp.Visualization.plot_dvh(my_plan, dose_1d=ecl_dose_1d_corr, struct_names=struct_names, style='solid', ax=ax, norm_flag=True)
ax = pp.Visualization.plot_dvh(my_plan, dose_1d=dose_sparse_corr_1d, struct_names=struct_names, style='dotted', ax=ax, norm_flag=True)
ax.set_title('- Eclipse .. PortPy')
plt.show()

'''
5) Comparing the PortPy plan against the benchmark IMRT plan for validation and analysis

We can compare the PortPy-generated plan with the benchmark IMRT plan provided in the PortPy dataset. The benchmark IMRT plan is generated using the MSK in-house automated planning system ECHO ([YouTube Video](https://youtu.be/895M6j5KjPs), [paper](https://aapm.onlinelibrary.wiley.com/doi/epdf/10.1002/mp.13572)). 
Before the comparison, we need to import the benchmark plan into Eclipse first.

'''

print('Done!')



