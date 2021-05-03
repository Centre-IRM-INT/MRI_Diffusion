
function create_slspec(json_file_name,output_name) % create_slspec('sub-01_ses-01_acq-AP_dwi.json')

fp = fopen(json_file_name,'r');
fcont = fread(fp);
fclose(fp);
cfcont = char(fcont');
i1 = strfind(cfcont,'SliceTiming');
i2 = strfind(cfcont(i1:end),'[');
i3 = strfind(cfcont((i1+i2):end),']');
cslicetimes = cfcont((i1+i2+1):(i1+i2+i3-2));
slicetimes = textscan(cslicetimes,'%f','Delimiter',',');
[sortedslicetimes,sindx] = sort(slicetimes{1});
mb = length(sortedslicetimes)/(sum(diff(sortedslicetimes)~=0)+1);
slspec = reshape(sindx,[mb length(sindx)/mb])'-1;
dlmwrite(output_name,slspec,'delimiter',' ','precision','%3d');
exit;