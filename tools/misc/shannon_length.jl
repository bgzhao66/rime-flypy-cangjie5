# Read in a file consistint of lines of text and calculate the Shannon length of each line.
# The Shannon length is defined as the number of bits required to encode the line using an optimal
# prefix-free code, such as Huffman coding.
# 
# The overall Shannon length is given by the formula:
# L = -∑(p(x) * log2(p(x))) for all unique characters x in the line
# where p(x) is the probability of character x in the line.
# The program should output the Shannon length for each line in the file.
# Usage: julia shannon_length.jl <filename>
#
# The Shannon length of every word is given by the formula:
# L(word) = -log2(p(word)))/log2(26) for each phrase in the file
# where p(c) is the probability of the code c in the file.
#
# There might be multiple different codes for the same word, in that case we take the code
# with the highest frequency.
# 
# The different codes of the same word are separated by a space, and sorted in desceding order alphabetically within the same line. And the maximum length of the codes of the word is considered as the length of the actual minimum code. In ouptut file, it appears in the fourth column, with a name as 'key_length'.
#
# Each line contains a word, which is sorted in descending order by frequency.
#
# The input file is a tab-separated file with three columns: word, code, frequency.
#
# Example input file:
# chinese_word\tcode\tfrequency
# 你好\tnihao\t10
# 世界\tshijie\t5
# 你好世界\tnihaoshijie\t2
#
# In order to prevent log2(0) we add a pseudocount of 1 to each code frequency.
# 
# The fields from the input file appear in the  output file as the first three columns. The output file is a tab-separated file with four columns: word, code, frequency, key_length, shannon_length, shannon_length_ceiling. 
# * The 'word' column is the word from the input file.
# * The 'codes' column is the codes from the input file, sorted in alphabetical order, and separated by a space.
# * The 'frequency' column is the frequency of the code in the input file plus one (pseudocount).
# * The 'key_length' column is the length of the shortest code of the words. 
# * The 'shannon_length' column is the Shannon length of the word calculated using the formula L(word). 
# * The 'shannon_length_ceiling' column is the ceiling of the Shannon length.
#
# The output file should be named as <input_filename>.shannon_length.csv with its header as:
# word\tcodes\tfrequency\tkey_length\tshannon_length\tshannon_length_ceiling
# Example output file:
# word\tcodes\tfrequency\tkey_length\tshannon_length\tshannon_length_ceiling
# 你好\tnihao\t11\t5\t1.4594316186372973\t2
# 世界\tshijie\t6\t6\t2.584962500721156\t3
# 你好世界\tnihaoshijie\t3\t10\t4.169925001442312\t5
# Note that the frequency column is the frequency from the input file plus one (pseudocount).

using Statistics
using DataFrames
using CSV
using Logging
using Dates
using ArgParse
using Plots
using Profile
using KernelDensity

function shannon_length(p)
	return -log2(p)/log2(26)
end

function process_file(input_filename::String)
	# Read the input file
	df = CSV.read(input_filename, DataFrame; delim='\t', header=false)
	rename!(df, [:word, :code, :frequency])
	
	# Add pseudocount of 1 to frequency
	df.frequency .+= 1
	# group by word and code, maximum frequency for each word-code pair
	df = combine(groupby(df, [:word, :code]), :frequency => maximum => :frequency)
	return df
end

function group_and_calculate(df::DataFrame)
	# Group by word and aggregate codes and frequencies
	grouped = combine(groupby(df, :word), 
					  :code => (x -> join(sort(x), " ")) => :codes,
					 :frequency => maximum => :frequency,
					  :code => (x -> minimum(length.(x))) => :key_length,
					  :word => (x -> length.(first(x))) => :word_length)
	
	# Calculate total frequency for probability calculation
	total_frequency = sum(grouped.frequency)
	
	# Calculate Shannon length and its ceiling
	grouped.shannon_length = shannon_length.(grouped.frequency ./ total_frequency)
	# round it with 2 decimal digits
	grouped.shannon_length = round.(grouped.shannon_length, digits=2)
	grouped.shannon_length_ceiling = Int.(ceil.(grouped.shannon_length))

	# add column indicating the ratio of key_length to word_length
	grouped.key_length_to_word_length = round.(grouped.key_length ./ grouped.word_length, digits=2)

	# Sort by descending frequency
	sort!(grouped, :frequency, rev=true)
	sort!(grouped, :word_length)

	return grouped
end

# Plot the distribution of ratio of key_length to word_length
function plot_distribution(df::DataFrame, input_filename::String)
	# Create a density plot
	df_sum = combine(groupby(df, :key_length_to_word_length), :frequency => sum => :total_frequency)
	# Perform kernel density estimation with weights
	kd = kde(df_sum.key_length_to_word_length, weights=df_sum.total_frequency)
	# Plot the density
	plot(kd.x, kd.density, xlabel="Key Length Per Character", ylabel="Density", title="Distribution of Key Length Per Character", legend=false)
	# Add a vertical line for the average	
	avg_ratio = sum(df.key_length_to_word_length .* df.frequency) / sum(df.frequency)
	vline!([avg_ratio], label="Average Ratio: $(round(avg_ratio, digits=2))", line=:dash, color=:red)
	# Add a text box with the average value
	annotate!([(avg_ratio + 0.05, maximum(kd.density) * 0.9, text("Avg: $(round(avg_ratio, digits=2))", :left, 10, :red))])
	# Set x-axis limits
	xlims!(0, maximum(df.key_length_to_word_length) + 0.1)
	# Set y-axis limits
	ylims!(0, maximum(kd.density) * 1.1)
	# Use a theme
	theme(:default)
	# Use a larger font size
	#plot!(fontsize=12)
	# Use a larger figure size
	size=(800, 600)
	# Use a different color scheme
	plot!(color=:blue)
	# Use a different line style
	plot!(linestyle=:solid)
	# Use a different marker style
	plot!(marker=:circle)
	# Add a legend
	#legend!(:topright)
	# Save the plot
	savefig(input_filename * "_key_length_to_word_length.png")
end	

function sum_zipped_prod(x, y)
	return sum(x .* y)
end

# Plot distribution of word count per code
# the data frame has columns: word, code, frequency
# This is to see how many words share the same code
function plot_word_count_per_code(df::DataFrame, input_filename::String)
	#CSV.write(input_filename * "_processed.csv", df; delim='\t')
	#println("Processed data written to: " * input_filename * "_processed.csv")
	# Group by code and count the number of words per code
	code_grouped = combine(groupby(df, :code), 
						   nrow => :word_count,
						   :frequency => sum => :total_frequency,
						   :frequency => (x -> sum(x) - maximum(x)) => :duplicate_frequency)

	# Sort by descending word count
	sort!(code_grouped, :word_count, rev=true)
	CSV.write(input_filename * "_code_word_count.csv", code_grouped; delim='\t')
	println("Code word count written to: " * input_filename * "_code_word_count.csv")

	# Create a density plot of word count per code with frequency considered
	# Calculate average word count per code with frequency considered
	avg_word_count = sum(code_grouped.word_count .* code_grouped.duplicate_frequency) / sum(code_grouped.total_frequency)
	# Perform kernel density estimation with weights
	kd = kde(code_grouped.word_count, weights=code_grouped.total_frequency)	

	# Plot the density
	plot(kd.x .- 1, kd.density, xlabel="Duplicate Count Per Code", ylabel="Density", title="Distribution of Duplicate Count Per Code", legend=false)
	# Add a vertical line for the average
	
	vline!([avg_word_count], label="Average Duplicate Count: $(round(avg_word_count, digits=5))", line=:dash, color=:red)
	# Add a text box with the average value
	annotate!([(avg_word_count + 0.5, maximum(kd.density) * 0.9, text("Avg: $(round(avg_word_count, digits=5))", :left, 10, :red))])
	# Set x-axis limits
	xlims!(0, maximum(code_grouped.word_count) + 1)
	# Set y-axis limits
	ylims!(0, maximum(kd.density) * 1.1)
	# Use a theme
	theme(:default)
	# Use a larger font size
	#plot!(fontsize=12)
	# Use a larger figure size
	size=(800, 600)
	# Use a different color scheme
	plot!(color=:green)
	# Use a different line style
	plot!(linestyle=:solid)
	# Use a different marker style
	plot!(marker=:circle)
	# Add a legend
	#legend!(:topright)
	# Save the plot
	savefig(input_filename * "_word_count_per_code.png")
	return avg_word_count
end

# Compute the average Shannon length and key length with frequency considered and print them
function compute_averages(df::DataFrame)
	avg_shannon_length = sum(df.shannon_length_ceiling .* df.frequency) / sum(df.frequency)
	avg_key_length = sum(df.key_length .* df.frequency) / sum(df.frequency)
	avg_code_length = sum((df.key_length ./ df.word_length) .* df.frequency) / sum(df.frequency)	
	println("Average Shannon Length: $avg_shannon_length")
	println("Average Key Length: $avg_key_length")
	println("Average Code Length (Key Length / Word Length): $avg_code_length")
end

function profile_main()
	Profile.clear()
	@profile main()
	Profile.print()
end

function main()
	# Parse command line arguments
	s = ArgParseSettings()

	@add_arg_table! s begin
		"input_file"
			help = "Input file to process"
			arg_type = String
			required = true
	end
	args = parse_args(ARGS, s)
	
	# Process each input file
	input_file = args["input_file"]
	df = process_file(input_file)
	# Plot word count per code
	avg_dup = plot_word_count_per_code(df, input_file)
	println("Average Duplicate Count Per Code: $avg_dup")
	# Group and calculate Shannon lengths
	grouped_df = group_and_calculate(df)
	compute_averages(grouped_df)
	# Plot distributions
	plot_distribution(grouped_df, input_file)

	# Prepare output filename
	output_filename = input_file * ".shannon_length.csv"
	# Write to output file
	CSV.write(output_filename, grouped_df; delim='\t')
	println("Processed file: $input_file -> $output_filename")

end

main()

