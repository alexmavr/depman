
def coords_from_name(core_name):
    index = int(core_name[3:])
    base_index = index / 2
    tile_row = base_index / 6
    column = base_index % 6
    row = tile_row * 2 + index % 2
    return row, column

'''
assert coords_from_name('rck00') == (0,0)
assert coords_from_name('rck01') == (1,0)
assert coords_from_name('rck02') == (0,1)
assert coords_from_name('rck03') == (1,1)
assert coords_from_name('rck04') == (0,2)
assert coords_from_name('rck05') == (1,2)
assert coords_from_name('rck06') == (0,3)
assert coords_from_name('rck07') == (1,3)
assert coords_from_name('rck08') == (0,4)
assert coords_from_name('rck09') == (1,4)
assert coords_from_name('rck10') == (0,5)
assert coords_from_name('rck11') == (1,5)
assert coords_from_name('rck12') == (2,0)
assert coords_from_name('rck13') == (3,0)
assert coords_from_name('rck14') == (2,1)
assert coords_from_name('rck15') == (3,1)
assert coords_from_name('rck16') == (2,2)
assert coords_from_name('rck17') == (3,2)
assert coords_from_name('rck18') == (2,3)
assert coords_from_name('rck19') == (3,3)
assert coords_from_name('rck20') == (2,4)
assert coords_from_name('rck21') == (3,4)
assert coords_from_name('rck22') == (2,5)
assert coords_from_name('rck23') == (3,5)
assert coords_from_name('rck24') == (4,0)
assert coords_from_name('rck25') == (5,0)
assert coords_from_name('rck26') == (4,1)
assert coords_from_name('rck27') == (5,1)
assert coords_from_name('rck36') == (6,0)
assert coords_from_name('rck37') == (7,0)
assert coords_from_name('rck43') == (7,3)
assert coords_from_name('rck44') == (6,4)

'''

def name_from_coords(x, y):
    base_x = x  - (x % 2)
    count = 2*y
    if base_x >= 2:
        count += (base_x/2) * 12
    count += x % 2
    return 'rck' + str(count).zfill(2)

'''
for x in range(8):
    for y in range(6):
        assert coords_from_name(name_from_coords(x, y)) == (x, y)
'''


def allocate_tasks(num_tasks, initial_cores):
    ''' allocates num_tasks jobs on a grid of SCC cores in a thermal aware manner '''

    def flatten(l):
        return [item for sublist in l for item in sublist]

    def manhattan_distance(x, y, x2, y2):
        return abs(x2 - x) + abs(y2 - y)

    all_cores =  ['rck'+str(i).zfill(2) for i in range(48)]

    Matrix = [[1000 for x in xrange(6)] for x in xrange(8)]

    for core in all_cores:
        if core not in initial_cores:
            x, y = coords_from_name(core)
            Matrix[x][y] = -1

# NO guards: cores must be placeable
# try to place the first core on a corner or side
    if Matrix[0][0] != -1:
        i = j = 0
    elif Matrix[0][5] != -1:
        i = 0
        j = 5
    elif Matrix[7][0] != -1:
        i = 7
        j = 0
    elif Matrix[7][5] != -1:
        i = 7
        j = 5
    else:
        i = j = 0
        while Matrix[i][j] == -1:
            j += 1
            if (j == 5):
                i += 1
                j = 0

    while num_tasks > 0:
        Matrix[i][j] = -2
        num_tasks -= 1
        for x in range(8):
            for y in range(6):
                if Matrix[x][y] > 0 :
                    r = manhattan_distance(i,j,x,y)
                    if r < Matrix[x][y]:
                        Matrix[x][y] = r
                    elif r - 1 < Matrix[x][y] <= r:
                        Matrix[x][y] -= 0.01

        max_list = []

        for x in range(8):
            for y in range(6):
                if Matrix[x][y] == max(flatten(Matrix)):
                    max_list.append((x,y))

        distance_to_edge = map(lambda (x,y):min([x,y,7-x,5-y]), max_list)

        min_list = []
        for x,y in max_list:
                if min([x,y,7-x,5-y]) == min(distance_to_edge):
                    min_list.append((x,y))

        from random import choice
        i,j = choice(min_list)

    for i in range(8):
        for j in range(6):
            if 0 < Matrix[i][j] :
                Matrix[i][j] = 0


    result = []
    for i in range(8):
        print Matrix[i]
        for j in range(6):
            if Matrix[i][j] == -2:
                print i,j
                result.append(name_from_coords(i, j))
    return result
