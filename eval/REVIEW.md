# Test set: review sheet

100 questions: 50 concept, 50 computation. Answers were computed by SymPy from each problem's `solution` in `questions.json`.

Check: is each question clear, is the expected section right, and is each answer right?

## Concept questions (scored by whether the expected section is in the top 5)

| ID | Question | Expected section |
|---|---|---|
| C01 | How do you find the distance between two points in 3D space? | 9.2 |
| C02 | How is the dot product related to the angle between two vectors? | 9.3 |
| C03 | How can you tell from the dot product whether two vectors are perpendicular? | 9.3 |
| C04 | What is the difference between the scalar projection and the vector projection of one vector onto another? | 9.3 |
| C05 | Why does the scalar projection formula divide by the length of the vector you're projecting onto? | 9.3 |
| C06 | What does the magnitude of the cross product tell you geometrically? | 9.4 |
| C07 | How is the cross product used to compute torque? | 9.4 |
| C08 | How do you write the equation of a plane if you know a point on it and a normal vector? | 9.5 |
| C09 | In 3D, what does an equation with one variable missing, like x^2 + y^2 = 4, describe? | 9.2, 9.6 |
| C10 | How do you recognize which quadric surface an equation describes, such as a paraboloid, a cone or a hyperboloid? | 9.6, 11.1 |
| C11 | What is a vector-valued function, and how does it trace out a curve in space? | 10.1 |
| C12 | How can you parametrize the curve where two surfaces intersect? | 10.1 |
| C13 | How do you get velocity, speed and acceleration from a position vector r(t)? | 10.4 |
| C14 | What are level curves, and how does a contour map show a function of two variables? | 11.1, 9.6 |
| C15 | What does a partial derivative measure? | 11.3 |
| C16 | Are the mixed partial derivatives f_xy and f_yx always equal? | 11.3 |
| C17 | How do you find the equation of the tangent plane to z = f(x, y) at a point? | 11.4 |
| C18 | How can you use a linear approximation to estimate the value of a function near a point where you know its value? | 11.4, 11.5 |
| C19 | How does the chain rule work for a function of x and y when x and y both depend on t? | 11.5, 11.6 |
| C20 | What is a directional derivative, and how do you compute one? | 11.6 |
| C21 | In which direction does a function increase fastest, and what is that maximum rate of increase? | 11.6 |
| C22 | Why is the gradient perpendicular to level curves? | 11.6 |
| C23 | How do you find the critical points of a function of two variables? | 11.7 |
| C24 | How does the second derivative test classify a critical point as a local max, a local min or a saddle point? | 11.7 |
| C25 | What is the Hessian matrix, and what does its determinant tell you? | 11.7 |
| C26 | What does a double integral represent geometrically? | 12.1, 12.2 |
| C27 | How do you set up an iterated integral over a region that isn't a rectangle? | 12.3 |
| C28 | How can symmetry make a double integral equal to zero without computing it? | 12.1 |
| C29 | When should you switch a double integral to polar coordinates, and what does dA become? | 12.4 |
| C30 | How do you find the volume of a solid with a double integral? | 12.1, 12.3 |
| C31 | How do you set up a triple integral and choose the order of integration? | 12.7 |
| C32 | How do you find the mass of a solid whose density varies from point to point? | 12.7, 12.3 |
| C33 | What is the volume element in spherical coordinates, and where does the rho^2 sin(phi) factor come from? | 12.8 |
| C34 | How do you decide between cylindrical and spherical coordinates for a triple integral? | 12.8 |
| C35 | What is a vector field, and what is a gradient field? | 13.1 |
| C36 | What does the line integral of a vector field along a curve measure physically? | 13.2 |
| C37 | What is the Fundamental Theorem for line integrals? | 13.3 |
| C38 | How do you find a potential function for a conservative vector field? | 13.3 |
| C39 | What conditions does a curve need to satisfy for Green's theorem to apply? | 13.4 |
| C40 | Why can Green's theorem fail when the vector field has a singularity inside the curve? | 13.4 |
| C41 | Why doesn't zero curl always mean a vector field is conservative? | 13.5a, 13.3, 13.4 |
| C42 | What does the divergence of a vector field measure? | 13.5b |
| C43 | What does a flux integral measure? | 13.6a |
| C44 | How can you tell the sign of a flux integral without computing it? | 13.6a, 13.6b |
| C45 | How do you compute the flux through a surface given as a graph z = f(x, y)? | 13.6b |
| C46 | What does Stokes' theorem say? | 13.7 |
| C47 | How does the Divergence Theorem deal with a singularity, like a field that blows up at the origin? | 13.8 |
| C48 | If I put a tiny paddle wheel in a flowing fluid, what tells me how fast it spins? *(no keywords)* | 13.5a |
| C49 | How do I measure how much fluid is flowing out of a tiny box around a point? *(no keywords)* | 13.5b |
| C50 | On a mountain whose height is z = f(x, y), which way should I walk to climb as steeply as possible? *(no keywords)* | 11.6 |

## Computation problems (answers auto-graded with SymPy)

| ID | Problem | Section | Method | Answer (SymPy) | Grading |
|---|---|---|---|---|---|
| P01 | Find the distance between the points (1, 2, 3) and (4, 6, 15). | 9.2 | 3D distance formula | `13` | value |
| P02 | Find the dot product of u = <2, -1, 3> and v = <4, 0, -2>. | 9.3 | dot product from components | `2` | value |
| P03 | Find the angle, in radians, between u = <1, 1, 0> and v = <1, 0, 1>. | 9.3 | angle from cos(theta) = u.v / (|u||v|) | `pi/3` | value |
| P04 | Find the scalar projection of b = <3, 0, 4> onto a = <2, 1, 2>. | 9.3 | scalar projection b.a / |a| | `14/3` | value |
| P05 | Find the vector projection of b = <1, 2, 3> onto a = <1, 1, 0>. | 9.3 | vector projection (b.a / |a|^2) a | `(3/2, 3/2, 0)` | vector |
| P06 | Find the cross product <1, 2, 3> x <4, 5, 6>. | 9.4 | cross product by the determinant | `(-3, 6, -3)` | vector |
| P07 | Find the area of the parallelogram spanned by <1, 0, 2> and <0, 3, 1>. | 9.4 | area = |u x v| | `sqrt(46)` | value |
| P08 | Find an equation of the plane through (1, -1, 2) with normal vector <3, 2, -1>. | 9.5 | plane n . (r - r0) = 0 | `3*x + 2*y - z + 1` | equation |
| P09 | Find an equation of the plane through the points (1, 0, 0), (0, 2, 0) and (0, 0, 3). | 9.5, 9.4 | normal = cross product of two edge vectors, then point-normal form | `6*x + 3*y + 2*z - 6` | equation |
| P10 | Find the torque about the origin when the force F = <0, 0, -10> is applied at the position r = <2, 1, 0>. | 9.4 | torque = r x F | `(-10, 20, 0)` | vector |
| P11 | Find the velocity vector of r(t) = <cos t, sin t, t> at t = pi/2. | 10.4, 10.1 | velocity = r'(t) | `(-1, 0, 1)` | vector |
| P12 | Find the speed of a particle with position r(t) = <t^2, 2t, ln t> at t = 1. | 10.4 | speed = |r'(t)| | `3` | value |
| P13 | Find the arc length of the helix r(t) = <3 cos t, 3 sin t, 4t> for 0 <= t <= 2 pi. | 10.4, 10.1 | arc length = integral of |r'(t)| dt | `10*pi` | value |
| P14 | Find f_x for f(x, y) = x^3 y^2 + sin(x y). | 11.3 | partial derivative: treat y as a constant | `y*(3*x**2*y + cos(x*y))` | expression |
| P15 | Find f_xy for f(x, y) = x^2 e^(3y). | 11.3 | mixed second partial f_xy | `6*x*exp(3*y)` | expression |
| P16 | Find an equation of the tangent plane to z = x^2 + y^2 at the point (1, 2, 5). | 11.4 | tangent plane z - f(a,b) = f_x(x-a) + f_y(y-b) | `2*x + 4*y - z - 5` | equation |
| P17 | Use the linear approximation of f(x, y) = sqrt(x^2 + y^2) at (3, 4) to estimate f(3.1, 3.9). | 11.4, 11.5 | linearization L(x, y) to estimate a nearby value | `249/50` | value |
| P18 | If z = x^2 y with x = cos t and y = sin t, find dz/dt at t = 0. | 11.5, 11.6 | chain rule dz/dt = z_x x' + z_y y' | `1` | value |
| P19 | Find the gradient of f(x, y) = x^2 y + 3y at the point (1, 2). | 11.6 | gradient = (f_x, f_y) at the point | `(4, 4)` | vector |
| P20 | Find the directional derivative of f(x, y) = x^2 y at (1, 2) in the direction of the vector <3, 4>. | 11.6 | directional derivative = grad f . unit vector | `16/5` | value |
| P21 | Find the maximum rate of change of f(x, y, z) = x y z at the point (1, 2, 3). | 11.6 | maximum rate of change = |grad f| | `7` | value |
| P22 | Find the unit vector in the direction in which f(x, y) = x^2 + 3xy increases fastest at the point (1, 1). | 11.6 | direction of fastest increase = grad f / |grad f| | `(5*sqrt(34)/34, 3*sqrt(34)/34)` | vector |
| P23 | Find the critical point of f(x, y) = x^2 + xy + y^2 - 3x. | 11.7 | solve f_x = 0 and f_y = 0 | `(2, -1)` | vector |
| P24 | For f(x, y) = x^3 + y^3 - 3xy, find the value of the second-derivative-test discriminant D = f_xx f_yy - (f_xy)^2 at the critical point (1, 1). | 11.7 | second derivative test D = f_xx f_yy - f_xy^2 | `27` | value |
| P25 | Evaluate the iterated integral of x y, with y from 0 to x and then x from 0 to 1. | 12.3 | iterated integral with a variable inner bound (Type I region) | `1/8` | value |
| P26 | Find the volume under the surface z = 4 - x^2 - y^2 and above the square 0 <= x <= 1, 0 <= y <= 1. | 12.1 | volume = double integral over a rectangle, done as an iterated integral | `10/3` | value |
| P27 | Evaluate the double integral of e^(x^2 + y^2) over the disk x^2 + y^2 <= 1. | 12.4 | switch to polar coordinates, dA = r dr dtheta | `pi*(-1 + E)` | value |
| P28 | Find the volume of the solid under z = x^2 + y^2 and above the disk of radius 2 centered at the origin. | 12.4 | volume over a disk in polar coordinates | `8*pi` | value |
| P29 | Evaluate the double integral of x over the region between y = x^2 and y = x for 0 <= x <= 1. | 12.3 | Type I region between two curves | `1/12` | value |
| P30 | Evaluate the integral from y = 0 to 1 of the integral from x = y to 1 of e^(x^2) dx dy. (Hint: reverse the order of integration.) | 12.3 | reverse the order of integration | `-1/2 + E/2` | value |
| P31 | Find the volume of the tetrahedron bounded by the coordinate planes and the plane x + y + z = 1. | 12.7 | triple integral under a plane in the first octant | `1/6` | value |
| P32 | Find the mass of the cube 0 <= x, y, z <= 1 with density delta(x, y, z) = x + y + z. | 12.7 | mass = triple integral of the density | `3/2` | value |
| P33 | Use cylindrical coordinates to find the volume inside the cylinder x^2 + y^2 = 4 between z = 0 and z = 3. | 12.8 | cylindrical coordinates, dV = r dz dr dtheta | `12*pi` | value |
| P34 | Find the volume of the solid inside the cone z = sqrt(x^2 + y^2) and below the plane z = 2. | 12.8 | cone volume in cylindrical (or spherical) coordinates | `8*pi/3` | value |
| P35 | Evaluate the line integral of F(x, y) = <x, y> along the line segment from (0, 0) to (3, 4). | 13.2, 13.3 | parametrize the segment (or use a potential, or the field is parallel to the path) | `25/2` | value |
| P36 | Find the work done by the force F(x, y, z) = <y, z, x> along the curve r(t) = <t, t^2, t^3> for 0 <= t <= 1. | 13.2 | parametric method: integrate F(r(t)) . r'(t) dt | `89/60` | value |
| P37 | Evaluate the line integral of F(x, y) = <-y, x> counterclockwise around the circle of radius 2 centered at the origin. | 13.2, 13.4 | the field is tangent to the circle (geometry), or Green's theorem | `8*pi` | value |
| P38 | Find a potential function for F(x, y) = <2xy + 1, x^2 + 3y^2>. | 13.3 | find the potential by integrating and checking | `x**2*y + x + y**3` | potential |
| P39 | The field F(x, y, z) = <2x, 2y, 2z> is conservative. Find its line integral along any path from (0, 0, 0) to (1, 2, 3). | 13.3 | Fundamental Theorem of Line Integrals: f(end) - f(start) | `14` | value |
| P40 | Use Green's theorem to evaluate the line integral of x y dx + x^2 dy around the boundary of the square [0, 1] x [0, 1], counterclockwise. | 13.4 | Green's theorem: double integral of Q_x - P_y | `1/2` | value |
| P41 | Use Green's theorem to find the area enclosed by the ellipse x^2/9 + y^2/4 = 1. | 13.4 | Green's theorem with Q_x - P_y = 1 gives the area (the notes show Green's theorem, not this exact area formula) | `6*pi` | value |
| P42 | Find the divergence of F(x, y, z) = <x^2, x y, z^3>. | 13.5b | divergence = P_x + Q_y + R_z | `3*x + 3*z**2` | expression |
| P43 | Find the curl of F(x, y, z) = <x y, y z, z x>. | 13.5a | curl by the determinant | `(-y, -z, -x)` | vector |
| P44 | Find the upward flux of F(x, y, z) = <0, 0, z> through the part of the plane z = 2 above the square 0 <= x <= 1, 0 <= y <= 1. | 13.6a, 13.6b | flat surface: n = k, so flux = (F . n) x area | `2` | value |
| P45 | Find the outward flux of F(x, y, z) = <x, y, z> through the sphere of radius 2 centered at the origin. | 13.6a, 13.8 | radial field on a sphere: F . n is constant (or the Divergence Theorem) | `32*pi` | value |
| P46 | Find the upward flux of F(x, y, z) = <x, y, z> through the part of the paraboloid z = 1 - x^2 - y^2 above the xy-plane. | 13.6b | shadow method for a graph z = g(x, y), then polar | `3*pi/2` | value |
| P47 | Use the Divergence Theorem to find the outward flux of F(x, y, z) = <x^3, y^3, z^3> through the unit sphere. | 13.8 | Divergence Theorem, then spherical coordinates | `12*pi/5` | value |
| P48 | Use the Divergence Theorem to find the outward flux of F(x, y, z) = <x y, y z, x z> through the boundary of the unit cube [0, 1]^3. | 13.8 | Divergence Theorem over a box | `3/2` | value |
| P49 | Use Stokes' theorem to find the circulation of F(x, y, z) = <-y, x, z> around the circle x^2 + y^2 = 1 in the plane z = 0, counterclockwise as seen from above. | 13.7 | Stokes' theorem with the flat disk as the surface | `2*pi` | value |
| P50 | Use Stokes' theorem to find the flux of curl F through the upper hemisphere x^2 + y^2 + z^2 = 1, z >= 0, oriented upward, for F(x, y, z) = <z, x, y>. | 13.7 | Stokes' theorem: swap the surface for the boundary circle (or a flat disk) | `pi` | value |

Grading kinds: **value** and **vector** must match exactly (numerically, to 1e-6); **expression** must be the same function; **equation** may differ by a constant factor (3x + 2y = 1 and 6x + 4y = 2 are the same plane); **potential** may differ by an added constant.
